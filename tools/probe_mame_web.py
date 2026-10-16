"""Banco aislado para comprobar los controladores MAME web con ROMs propias."""
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

DRIVERS = {
    "barline": ("nbmj8688", "04276fe25bf6727711e59b9c2caf36a2418d004d", "5d4b1e9c4231e86080b69e86a577dc358ad6fa9d"),
    "cfever61": ("highvdeo", "f39dbf8956d437d44bf745dce4e33cc8f2a6f0d2", "859dc858107117647b7b99ddc4952c2ec6dc49ab"),
    "rcasino": ("caswin", "9c702260666c891394965576f7c028c94b87074b", "3e50251b63c8a0fe1b5cc2860112a86933dd4809"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    assert root.parent.is_dir()
    root.mkdir(exist_ok=True)
    if not args.serve:
        with httpx.Client(follow_redirects=True, timeout=120) as client:
            for code, (driver, js_hash, wasm_hash) in DRIVERS.items():
                for ext, expected in (("js", js_hash), ("wasm", wasm_hash)):
                    name = f"mame{driver}.{ext}"
                    target = root / name
                    if not target.is_file():
                        print(f"Preparando {name}", flush=True)
                        response = client.get(f"https://archive.org/download/emularity_engine_v1/{name}.gz")
                        response.raise_for_status()
                        assert hashlib.sha1(response.content).hexdigest() == expected
                        target.write_bytes(gzip.decompress(response.content))
                rom = root / f"{code}.zip"
                if not rom.exists():
                    response = client.get("http://192.168.0.47:8001/api/mame/download", params={"path": rom.name})
                    response.raise_for_status()
                    rom.write_bytes(response.content)
        with (root / "server.log").open("ab") as out:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(root), "--serve"],
                stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
        print(f"Banco iniciado: http://127.0.0.1:8691/<juego> PID {process.pid}")
        return

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            code = self.path.strip("/")
            if code in DRIVERS:
                driver = DRIVERS[code][0]
                html = '''<!doctype html><html><head><style>body{margin:0;background:#10111c;color:white}canvas{width:100vw;height:90vh;object-fit:contain}</style></head><body>
                <div id="status">Preparando MAME</div><canvas id="canvas" tabindex="0"></canvas><script>
                window.__mameLogs=[];
                const send=(event,message)=>window.chrome?.webview?.postMessage(JSON.stringify({event,message}));
                const log=text=>{window.__mameLogs.push(String(text));document.getElementById('status').textContent=String(text);};
                window.gameclubExit=()=>{JSMAME.exit();send('exit','');};
                fetch('/CODE.zip').then(r=>r.arrayBuffer()).then(rom=>{
                  window.Module={canvas:document.getElementById('canvas'),arguments:['CODE','-rompath','/roms','-nvram_directory','/nvram','-cfg_directory','/cfg','-state_directory','/sta','-window','-nokeepaspect','-resolution','1024x448','-skip_gameinfo','-video','soft'],
                    locateFile:name=>'/'+name,print:log,printErr:log,
                    preRun:[()=>{for(const p of ['/roms','/nvram','/cfg','/sta']){try{FS.mkdir(p);}catch(_){}}FS.writeFile('/roms/CODE.zip',new Uint8Array(rom));}],
                    onRuntimeInitialized:()=>{window.__runtime=true;},onAbort:error=>{log('ABORT '+error);send('error',String(error));}};
                  const script=document.createElement('script');script.src='/mameDRIVER.js';document.body.appendChild(script);
                  setInterval(()=>{try{if(JSMAME.get_machine()){window.__running=true;document.getElementById('canvas').focus();}}catch(_){}},500);
                }).catch(error=>log(String(error)));
                </script></body></html>'''.replace("CODE", code).replace("DRIVER", driver)
                body, content_type = html.encode(), "text/html"
            else:
                file = root / code
                if not file.is_file() or file.parent != root:
                    self.send_error(404)
                    return
                body = file.read_bytes()
                content_type = "application/wasm" if file.suffix == ".wasm" else "text/javascript" if file.suffix == ".js" else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
            self.end_headers()
            self.wfile.write(body)
    ThreadingHTTPServer(("127.0.0.1", 8691), Handler).serve_forever()


if __name__ == "__main__":
    main()
