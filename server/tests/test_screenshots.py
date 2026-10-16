import io
import httpx
from fastapi.testclient import TestClient
from PIL import Image
from app.main import create_app


def test_screenshots_are_gameplay_images_deduplicated_and_persistent(tmp_path,monkeypatch):
    original=httpx.AsyncClient
    image=io.BytesIO()
    Image.new("RGB",(16,16),"red").save(image,"PNG")
    requested=[]
    def respond(request):
        requested.append(request.url.path)
        if request.url.path.endswith("/"):
            return httpx.Response(200,text='<a href="Mario%20Kart%20DS%20(Europe).png">EU</a><a href="Mario%20Kart%20DS%20(USA).png">US</a>')
        return httpx.Response(200,content=image.getvalue())
    monkeypatch.setattr("app.thumbnails.httpx.AsyncClient",lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    paths=(tmp_path/"roms",tmp_path/"data",tmp_path/"media")
    app=create_app(*paths,token="token")
    with TestClient(app,headers={"Authorization":"Bearer token"}) as client:
        client.post("/api/systems/nds/upload",files={"file":("Mario Kart DS.nds",b"rom")})
        game=client.get("/api/games").json()[0]
        endpoint=f"/api/games/{game['id']}/screenshots"
        assert not client.get(endpoint).json()["checked"]
        result=client.post(endpoint+"/refresh")
        assert result.status_code==200
        assert result.json()["checked"]
        images=result.json()["images"]
        assert len(images)==1
        assert client.get(images[0]["url"]).headers["content-type"]=="image/jpeg"
        assert all("Named_Snaps" in path for path in requested if not path.endswith("/"))
        assert client.get(images[0]["url"],headers={"Authorization":""}).status_code==401
        uploaded=client.post(endpoint,files={"file":("Own.png",image.getvalue())})
        assert len(uploaded.json()["images"])==2
        assert client.get("/api/games").json()[0]["cover_url"] is None
        assert client.post(endpoint,files={"file":("not-image.png",b"no")}).status_code==422
    with TestClient(create_app(*paths,token="token"),headers={"Authorization":"Bearer token"}) as client:
        assert len(client.get(endpoint).json()["images"])==2
        assert client.get(images[0]["url"]).status_code==200
