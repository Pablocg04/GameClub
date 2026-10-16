import hashlib
import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .systems import SYSTEMS


class Library:
    def __init__(self, roms: Path, data: Path, media: Path):
        self.roms, self.data, self.media = roms.resolve(), data.resolve(), media.resolve()
        self.lock = threading.RLock()
        for directory in (self.roms, self.data, self.media):
            directory.mkdir(parents=True, exist_ok=True)
        self.database = self.data / "library.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS systems (id TEXT PRIMARY KEY, config TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS screenshots (
                    id TEXT PRIMARY KEY, game_id TEXT NOT NULL, file TEXT NOT NULL,
                    label TEXT NOT NULL, provider TEXT NOT NULL,
                    UNIQUE(game_id, provider, id)
                );
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY, system_id TEXT NOT NULL, path TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL, size INTEGER NOT NULL,
                    favorite INTEGER NOT NULL DEFAULT 0, cover TEXT,
                    description TEXT NOT NULL DEFAULT '', provider TEXT,
                    present INTEGER NOT NULL DEFAULT 1
                );
            """)
            if 'modified_ns' not in {row['name'] for row in db.execute('PRAGMA table_info(games)')}:
                db.execute('ALTER TABLE games ADD COLUMN modified_ns INTEGER NOT NULL DEFAULT 0')
            for config in SYSTEMS:
                db.execute("INSERT OR IGNORE INTO systems VALUES (?, ?)",
                           (config["id"], json.dumps(config)))
            defaults = {config["id"]: config for config in SYSTEMS}
            for row in db.execute("SELECT * FROM systems").fetchall():
                config = json.loads(row["config"])
                if "metadata_id" not in config:
                    config["metadata_id"] = config.pop("screenscraper_id", None) or defaults.get(row["id"], {}).get("metadata_id")
                    db.execute("UPDATE systems SET config=? WHERE id=?", (json.dumps(config), row["id"]))
            db.execute("DELETE FROM settings WHERE key IN ('screenscraper_account', 'screenscraper_developer')")
            db.execute("UPDATE settings SET value=? WHERE key='scrape_provider'", (json.dumps("auto"),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def systems(self):
        with self.connect() as db:
            counts = dict(db.execute("SELECT system_id, count(*) FROM games WHERE present=1 GROUP BY system_id"))
            return [dict(json.loads(row["config"]), game_count=counts.get(row["id"], 0))
                    for row in db.execute("SELECT * FROM systems ORDER BY id")]

    def setting(self, key):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row["value"]) if row else None

    def save_setting(self, key, value):
        with self.connect() as db:
            db.execute("""INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, json.dumps(value)))

    def get_system(self, id):
        return next((s for s in self.systems() if s["id"] == id), None)

    def add_system(self, config):
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO systems VALUES (?, ?)", (config["id"], json.dumps(config)))
            (self.roms / config["id"]).mkdir(exist_ok=True)

    def safe_path(self, relative):
        path = (self.roms / relative).resolve()
        if not path.is_relative_to(self.roms):
            raise ValueError("La ruta sale de la biblioteca")
        return path

    def scan(self):
        with self.lock, self.connect() as db:
            db.execute("UPDATE games SET present=0")
            for config in self.systems():
                folder = self.safe_path(config["id"])
                if not folder.is_dir():
                    continue
                files = [p for p in folder.rglob("*") if p.is_file()
                         and p.suffix.lower() in config["extensions"]
                         and p.resolve().is_relative_to(self.roms)]
                # Los tracks de un CUE y los discos de un M3U no son juegos separados.
                referenced = set()
                for p in files:
                    if p.suffix.lower() not in {".cue", ".m3u"}:
                        continue
                    if p.stat().st_size > 1024 * 1024:
                        continue
                    text = p.read_text(encoding="utf-8-sig", errors="replace")
                    names = (re.findall(r'FILE\s+"([^"]+)"', text, re.I)
                             + re.findall(r'FILE\s+([^\s"]+)\s+\w+', text, re.I)
                             if p.suffix.lower() == ".cue" else
                             [line.strip() for line in text.splitlines()
                              if line.strip() and not line.lstrip().startswith("#")])
                    referenced.update((p.parent / name.replace("\\", "/")).resolve() for name in names)
                for path in files:
                    if path.resolve() in referenced:
                        continue
                    if config["id"] == "mame" and path.suffix.lower() == ".chd" and (
                            (folder / f"{path.parent.name}.zip").is_file() or
                            (folder / f"{path.stem}.zip").is_file()):
                        continue  # Disco auxiliar de un romset, no otro juego.
                    relative = path.relative_to(self.roms).as_posix()
                    id = hashlib.sha256(relative.encode()).hexdigest()[:24]
                    title = re.sub(r"\s*[\[(].*?[\])]", "", path.stem).strip() or path.stem
                    stat = path.stat()
                    db.execute("""INSERT INTO games (id, system_id, path, title, size, modified_ns)
                        VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
                        size=excluded.size, modified_ns=excluded.modified_ns, present=1""",
                               (id, config["id"], relative, title, stat.st_size, stat.st_mtime_ns))
            count = db.execute("SELECT count(*) FROM games WHERE present=1").fetchone()[0]
        return count

    def games(self, system_id=None, query="", favorites=False):
        conditions, args = ["present=1"], []
        if system_id:
            conditions.append("system_id=?")
            args.append(system_id)
        if query:
            conditions.append("title LIKE ?")
            args.append(f"%{query}%")
        if favorites:
            conditions.append("favorite=1")
        with self.connect() as db:
            return [self.public(row) for row in db.execute(
                f"SELECT * FROM games WHERE {' AND '.join(conditions)} ORDER BY title COLLATE NOCASE", args)]

    @staticmethod
    def public(row):
        result = dict(row)
        result["favorite"] = bool(result["favorite"])
        result["filename"] = Path(result["path"]).name
        result['revision'] = str(result.pop('modified_ns', 0))
        result["cover_url"] = f"/api/games/{result['id']}/cover" if result["cover"] else None
        result.pop("cover")
        return result

    def game(self, id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM games WHERE id=? AND present=1", (id,)).fetchone()
            return dict(row) if row else None

    def update(self, id, **fields):
        if not fields.keys() <= {"title", "favorite", "description", "cover", "provider"}:
            raise ValueError("Campo no editable")
        with self.connect() as db:
            db.execute(f"UPDATE games SET {', '.join(f'{key}=?' for key in fields)} WHERE id=?",
                       [*fields.values(), id])

    def screenshots(self, game_id):
        with self.connect() as db:
            return [{"id":row["id"],"label":row["label"],"provider":row["provider"],
                     "url":f"/api/games/{game_id}/screenshots/{row['id']}"}
                    for row in db.execute("SELECT * FROM screenshots WHERE game_id=? ORDER BY rowid",(game_id,))]

    def add_screenshot(self, id, game_id, file, label, provider):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO screenshots VALUES (?,?,?,?,?)",(id,game_id,file,label,provider))

    def screenshot_file(self, game_id, id):
        with self.connect() as db:
            row=db.execute("SELECT file FROM screenshots WHERE game_id=? AND id=?",(game_id,id)).fetchone()
            return row["file"] if row else None
