from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_redirects_to_workspace() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui"


def test_workspace_page_is_served() -> None:
    response = client.get("/ui")
    assert response.status_code == 200
    assert "Government IDSS" in response.text
    assert 'id="document-upload-form"' in response.text
    assert 'id="media-search-form"' in response.text


def test_frontend_assets_are_served() -> None:
    css = client.get("/static/app.css")
    js = client.get("/static/app.js")
    assert css.status_code == 200
    assert "grid-template-columns" in css.text
    assert js.status_code == 200
    assert "/api/v1/search/evidence" in js.text
    assert "/api/v1/search/media-evidence" in js.text
