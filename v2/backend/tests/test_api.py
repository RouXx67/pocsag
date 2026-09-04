import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import get_db, engine
from app.models import Base

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db_session():
    test_engine = create_async_engine(TEST_DB_URL, echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with test_session_factory() as session:
        yield session

    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_version(client):
    r = await client.get("/api/version")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data


@pytest.mark.asyncio
async def test_config_defaults(client):
    r = await client.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert data["frequencies"] == ["85.955M", "173512.5k"]
    assert "AVP" in data["keywords"]
    assert data["notify_empty"] is True


@pytest.mark.asyncio
async def test_login_default(client):
    r = await client.post("/api/auth/login", json={"password": "admin"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong(client):
    r = await client.post("/api/auth/login", json={"password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_messages_empty(client):
    r = await client.get("/api/messages")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_update_config(client, db_session):
    token_r = await client.post("/api/auth/login", json={"password": "admin"})
    token = token_r.json()["access_token"]

    r = await client.post(
        "/api/config",
        json={"frequencies": ["85.955M"], "scan_interval": 15},
        params={"token": token},
    )
    assert r.status_code == 200

    r2 = await client.get("/api/config")
    data = r2.json()
    assert data["frequencies"] == ["85.955M"]
    assert data["scan_interval"] == 15


@pytest.mark.asyncio
async def test_aliases_crud(client):
    token_r = await client.post("/api/auth/login", json={"password": "admin"})
    token = token_r.json()["access_token"]

    r = await client.post(
        "/api/aliases", json={"ric": "0123456", "name": "VSAV Test"},
        params={"token": token},
    )
    assert r.status_code == 200

    r2 = await client.get("/api/aliases")
    data = r2.json()
    assert len(data) == 1
    assert data[0]["ric"] == "0123456"

    r3 = await client.delete(
        "/api/aliases/0123456", params={"token": token},
    )
    assert r3.status_code == 200

    r4 = await client.get("/api/aliases")
    assert len(r4.json()) == 0


@pytest.mark.asyncio
async def test_blacklist_crud(client):
    token_r = await client.post("/api/auth/login", json={"password": "admin"})
    token = token_r.json()["access_token"]

    r = await client.post(
        "/api/blacklist", json={"ric": "0099999"},
        params={"token": token},
    )
    assert r.status_code == 200

    r2 = await client.get("/api/blacklist")
    assert len(r2.json()) == 1

    r3 = await client.delete("/api/blacklist/0099999", params={"token": token})
    assert r3.status_code == 200

    r4 = await client.get("/api/blacklist")
    assert len(r4.json()) == 0


@pytest.mark.asyncio
async def test_stats_empty(client):
    r = await client.get("/api/stats")
    data = r.json()
    assert data["total_today"] == 0
    assert data["urgent_today"] == 0


@pytest.mark.asyncio
async def test_clear_logs(client):
    r = await client.post("/api/clear-logs")
    assert r.status_code == 200