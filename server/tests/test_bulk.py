import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.bulk import BulkScraper, best_candidate
from app.library import Library
from app.main import create_app
from app.scraper import ScraperError
from app.thumbnails import LibretroThumbnails


@pytest.fixture
def library(tmp_path):
    library = Library(tmp_path / "roms", tmp_path / "data", tmp_path / "media")
    (library.roms / "gba").mkdir()
    for name in ("Alpha", "Beta", "Gamma"):
        (library.roms / "gba" / f"{name}.gba").write_bytes(b"rom")
    library.scan()
    return library


def ready_scraper(library):
    return LibretroThumbnails(library.data)


def test_candidate_selection_avoids_ambiguity_and_sequels():
    assert best_candidate("Pokemon", [{"id": "1", "title": "Pokémon"}])["id"] == "1"
    assert best_candidate("Game", [{"id": "1", "title": "Game"}, {"id": "2", "title": "Game"}]) is None
    assert best_candidate("Final Fantasy IV", [{"id": "1", "title": "Final Fantasy V"}]) is None
    assert best_candidate("Some Game 2", [{"id": "1", "title": "Some Game 3"}]) is None
    assert best_candidate("Unknown", []) is None


def test_bulk_updates_matches_skips_existing_and_ambiguous(library):
    games = library.games()
    library.update(games[2]["id"], cover="existing.jpg", provider="manual")
    scraper = ready_scraper(library)
    applied = []

    async def search(title, system):
        assert system == 12
        return [{"id": "1", "title": title}] if title == "Alpha" else []

    async def cover(id, system):
        return {"title": "Alpha", "description": "Ficha"}, b"image"

    async def apply(id, metadata, image):
        applied.append(id)
        library.update(id, cover="new.jpg")

    scraper.search, scraper.cover = search, cover
    bulk = BulkScraper(library, scraper, apply)

    async def scenario():
        await bulk.start()
        await bulk.task
        result = bulk.public()
        assert result["status"] == "completed"
        assert result["total"] == 2
        assert result["updated"] == 1 and result["skipped"] == 1
        assert result["already_covered"] == 1
        assert "_pending" not in result

    asyncio.run(scenario())
    assert applied == [games[0]["id"]]
    assert library.game(games[2]["id"])["provider"] == "manual"


def test_bulk_network_pause_persists_and_resumes(library):
    scraper = ready_scraper(library)
    calls = []

    async def search(title, system):
        calls.append(title)
        raise ScraperError("El catálogo público no responde", stop_batch=True)

    async def apply(*args):
        raise AssertionError("No debe descargar si el catálogo no responde")

    scraper.search = search
    bulk = BulkScraper(library, scraper, apply)

    async def scenario():
        await bulk.start()
        await bulk.task
        assert bulk.public()["status"] == "paused"
        assert bulk.public()["can_resume"] is True
        assert bulk.public()["processed"] == 0
        assert calls == ["Alpha"]
        restored = BulkScraper(library, scraper, apply)

        async def empty_search(*args):
            return []

        scraper.search = empty_search
        await restored.start(resume=True)
        await restored.task
        assert restored.public()["status"] == "completed"
        assert restored.public()["processed"] == 3

    asyncio.run(scenario())


def test_bulk_cancel_and_single_job(library):
    scraper = ready_scraper(library)
    entered, release = None, None

    async def search(*args):
        entered.set()
        await release.wait()
        return []

    async def apply(*args):
        pass

    scraper.search = search
    bulk = BulkScraper(library, scraper, apply)

    async def scenario():
        nonlocal entered, release
        entered, release = asyncio.Event(), asyncio.Event()
        await bulk.start()
        await entered.wait()
        with pytest.raises(ValueError):
            await bulk.start()
        await bulk.cancel()
        release.set()
        await bulk.task
        assert bulk.public()["status"] == "cancelled"
        assert bulk.public()["processed"] == 1
        assert bulk.public()["can_resume"] is True

    asyncio.run(scenario())


def test_interrupted_job_can_resume(library):
    library.save_setting("bulk_scrape", {"status": "running", "_pending": [library.games()[0]["id"]]})

    async def apply(*args):
        pass

    bulk = BulkScraper(library, ready_scraper(library), apply)
    assert bulk.public()["status"] == "interrupted"
    assert bulk.public()["can_resume"] is True


def test_bulk_auth_and_reject_account_provider(tmp_path):
    app = create_app(tmp_path / "roms", tmp_path / "data", tmp_path / "media", token="token")
    with TestClient(app, headers={"Authorization": "Bearer token"}) as client:
        assert client.post("/api/scrape/job", json={"provider": "screenscraper"}).status_code == 422
        assert client.get("/api/scrape/job", headers={"Authorization": ""}).status_code == 401
        assert client.post("/api/scrape/job/cancel", headers={"Authorization": ""}).status_code == 401


def test_resume_old_provider_uses_public_catalog(library):
    library.save_setting("bulk_scrape", {"status": "paused", "provider": "screenscraper",
        "_pending": [library.games()[0]["id"]]})
    async def apply(*args): pass
    bulk = BulkScraper(library, ready_scraper(library), apply)
    assert bulk.public()["provider"] == "auto" and bulk.public()["can_resume"]
