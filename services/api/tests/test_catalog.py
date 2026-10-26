import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tooldawn.config import Settings
from tooldawn.main import create_app


@pytest.fixture
def client():
    settings = Settings(_env_file=None, environment="test", catalog_backend="seed", redis_url=None)
    with TestClient(create_app(settings)) as client:
        yield client


def test_search_category_and_pagination(client):
    response = client.get("/api/v1/tools", params={"category": "image", "limit": 1})
    assert response.status_code == 200
    first = response.json()
    assert first["total"] == 4
    assert first["next_cursor"] == 1
    second = client.get(
        "/api/v1/tools", params={"category": "image", "limit": 1, "cursor": 1}
    ).json()
    assert second["items"][0]["slug"] != first["items"][0]["slug"]
    assert second["next_cursor"] == 2


@pytest.mark.parametrize("query", ["%", "_", "不存在的工具"])
def test_search_treats_special_characters_literally(client, query):
    assert client.get("/api/v1/tools", params={"q": query}).json()["items"] == []


def test_search_english_keywords_and_whitespace(client):
    data = client.get("/api/v1/tools", params={"q": "  WEBP  "}).json()
    assert [item["slug"] for item in data["items"]] == ["image-compress"]


def test_categories_counts_match_catalog(client):
    categories = client.get("/api/v1/categories").json()
    assert (
        sum(item["tool_count"] for item in categories)
        == client.get("/api/v1/tools").json()["total"]
    )


def test_not_found_uses_public_error_and_request_id(client):
    response = client.get("/api/v1/tools/missing")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.json()["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("params", [{"limit": 1000}, {"cursor": -1}, {"q": "x" * 101}])
def test_input_limits(client, params):
    response = client.get("/api/v1/tools", params=params)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_parameters"


def test_recent_order_is_stable_and_featured_filter_works(client):
    tools = client.get("/api/v1/tools?sort=recent&featured=true").json()["items"]
    assert all(tool["featured"] for tool in tools)
    assert [tool["updated_at"] for tool in tools] == sorted(
        [tool["updated_at"] for tool in tools], reverse=True
    )


def test_unfinished_tools_are_not_advertised_as_available(client):
    tool = client.get("/api/v1/tools/photo-restyle").json()
    assert tool["status"] == "coming_soon"
    assert tool["external_url"] is None
    for slug in ("squoosh", "photopea", "excalidraw", "json-formatter"):
        assert client.get(f"/api/v1/tools/{slug}").status_code == 404
    assert all(t["kind"] == "internal" for t in client.get("/api/v1/tools").json()["items"])


def test_text_tools_expose_setup_state_without_prompts(client):
    tool = client.get("/api/v1/tools/text-polish").json()
    assert tool["status"] == "available"
    response = client.get("/api/v1/ai-tools/text-polish")
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert "instruction" not in response.json()
    assert client.get("/api/v1/ai-tools/photo-restyle").status_code == 404


def test_health_endpoints(client):
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    assert client.get("/api/v1/health/ready").json()["catalog_backend"] == "seed"


def test_production_cannot_use_seed_catalog():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", catalog_backend="seed")


def test_postgres_requires_connection_string():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, catalog_backend="postgres", database_url=None)
