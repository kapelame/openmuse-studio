from fastapi.testclient import TestClient

from openmuse_api.main import app
from openmuse_api.services.queue import QueueUnavailable


def test_project_upload_render_manifest(monkeypatch) -> None:
    async def no_redis(_payload):
        raise QueueUnavailable("test isolation")

    monkeypatch.setattr("openmuse_api.main.enqueue", no_redis)
    client = TestClient(app)
    created = client.post("/api/projects", json={"title": "API smoke", "description": "test", "creation_mode": "mv", "rights_confirmed": True})
    assert created.status_code == 200
    project = created.json()
    project_id = project["id"]
    with open("examples/demo-tone.wav", "rb") as audio:
        uploaded = client.post(f"/api/projects/{project_id}/assets", files={"file": ("demo.wav", audio, "audio/wav")}, data={"role": "source_audio"})
    assert uploaded.status_code == 200
    with open("examples/demo-cover.png", "rb") as cover:
        uploaded = client.post(f"/api/projects/{project_id}/assets", files={"file": ("cover.png", cover, "image/png")}, data={"role": "cover"})
    assert uploaded.status_code == 200
    with open("examples/demo.srt", "rb") as subtitles:
        uploaded = client.post(f"/api/projects/{project_id}/assets", files={"file": ("lyrics.srt", subtitles, "application/x-subrip")}, data={"role": "lyrics_timing"})
    assert uploaded.status_code == 200
    rendered = client.post(f"/api/projects/{project_id}/render", json={"template": "editorial-lyrics", "aspect_ratio": "1:1", "fps": 24})
    assert rendered.status_code == 200
    job_id = rendered.json()["job"]["id"]
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "succeeded"
    manifest = client.get(f"/api/projects/{project_id}/manifest")
    assert manifest.status_code == 200 and manifest.json()["api_keys_included"] is False


def test_lyrics_edit_and_export() -> None:
    client = TestClient(app)
    denied = client.post("/api/projects", json={"title": "No consent", "creation_mode": "mv"})
    assert denied.status_code == 422
    project = client.post("/api/projects", json={"title": "Lyrics API", "creation_mode": "mv", "rights_confirmed": True}).json()
    with open("examples/demo.srt", "rb") as subtitles:
        uploaded = client.post(f"/api/projects/{project['id']}/assets", files={"file": ("lyrics.srt", subtitles, "application/x-subrip")}, data={"role": "lyrics_timing"})
    assert uploaded.status_code == 200
    document = client.get(f"/api/projects/{project['id']}").json()["lyrics"][0]
    cues = document["structured_lyrics"]
    cues[0]["text"] = "Edited fixture line"
    updated = client.patch(f"/api/projects/{project['id']}/lyrics/{document['id']}", json={"structured_lyrics": cues})
    assert updated.status_code == 200 and updated.json()["structured_lyrics"][0]["text"] == "Edited fixture line"
    exported = client.get(f"/api/projects/{project['id']}/lyrics/{document['id']}/export/srt")
    assert exported.status_code == 200 and "Edited fixture line" in exported.text
