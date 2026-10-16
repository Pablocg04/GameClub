import asyncio
import gzip
import hashlib

import httpx
import pytest
from fastapi import HTTPException

from app.library import Library
from app.mame_web import DRIVERS, MameWebAssets, plan


def test_mame_web_plan_uses_only_roms_in_our_library(tmp_path):
    library=Library(tmp_path/'roms',tmp_path/'data',tmp_path/'media')
    (library.roms/'mame').mkdir()
    (library.roms/'mame/barline.zip').write_bytes(b'owned rom')
    result=plan(library,{'path':'mame/barline.zip'})
    assert result['engine']=='mame_web'
    assert result['driver']=='nbmj8688'
    assert result['files'][0]['path']=='barline.zip'
    assert result['audit']=='runtime'
    assert plan(library,{'path':'mame/not_supported.zip'}) is None


def test_mame_web_assets_are_hash_checked_and_cached(tmp_path,monkeypatch):
    original=httpx.AsyncClient
    compressed=gzip.compress(b'our test engine')
    monkeypatch.setitem(DRIVERS['nbmj8688'],'js',hashlib.sha1(compressed).hexdigest())
    requests=[]
    def respond(request):
        requests.append(str(request.url))
        assert request.url.host=='archive.org'
        return httpx.Response(200,content=compressed)
    monkeypatch.setattr('app.mame_web.httpx.AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    assets=MameWebAssets(tmp_path)
    async def run():
        path=await assets.get('nbmj8688','mamenbmj8688.js')
        assert path.read_bytes()==b'our test engine'
        await assets.get('nbmj8688','mamenbmj8688.js')
        with pytest.raises(HTTPException) as error:
            await assets.get('unknown','anything.js')
        assert error.value.status_code==422
    asyncio.run(run())
    assert len(requests)==1
