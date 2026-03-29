"""SQLAlchemy async engine, session factory, and declarative base."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine(
    database_url: str,
    pool_size: int | None = None,
    max_overflow: int | None = None,
):
    """Create an async SQLAlchemy engine.

    Pool settings (pool_size, max_overflow) are only applied for non-SQLite
    databases because SQLite does not support connection pooling.
    """
    kwargs: dict = {"echo": False}
    if pool_size is not None and "sqlite" not in database_url:
        kwargs["pool_size"] = pool_size
    if max_overflow is not None and "sqlite" not in database_url:
        kwargs["max_overflow"] = max_overflow
    return create_async_engine(database_url, **kwargs)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
