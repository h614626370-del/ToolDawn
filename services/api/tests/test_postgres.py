import os

import pytest
from fastapi.testclient import TestClient

from tooldawn.config import Settings
from tooldawn.main import create_app

database_url = os.environ.get("TOOLDAWN_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not database_url, reason="Requires migrated, seeded test PostgreSQL"
)


def test_postgres_catalog_matches_seed_queries():
    postgres = create_app(
        Settings(
            _env_file=None,
            environment="test",
            catalog_backend="postgres",
            database_url=database_url,
            redis_url=None,
        )
    )
    seed = create_app(
        Settings(
            _env_file=None,
            environment="test",
            catalog_backend="seed",
            redis_url=None,
        )
    )
    with TestClient(postgres) as pg, TestClient(seed) as reference:
        assert pg.get("/api/v1/health/ready").status_code == 200
        assert pg.get("/api/v1/categories").json() == reference.get("/api/v1/categories").json()
        for params in [
            {},
            {"q": "压缩", "category": "image", "limit": 1},
            {"q": "  WEBP  "},
            {"q": "%"},
            {"q": "_"},
            {"q": "不存在的工具"},
            {"sort": "recent", "featured": True, "limit": 3, "cursor": 2},
        ]:
            response = pg.get("/api/v1/tools", params=params)
            assert response.status_code == 200
            assert response.json() == reference.get("/api/v1/tools", params=params).json()
        assert (
            pg.get("/api/v1/tools/squoosh").json() == reference.get("/api/v1/tools/squoosh").json()
        )
