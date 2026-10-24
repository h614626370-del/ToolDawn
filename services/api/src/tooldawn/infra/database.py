from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_database(url: str) -> tuple[AsyncEngine, async_sessionmaker]:
    engine = create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
