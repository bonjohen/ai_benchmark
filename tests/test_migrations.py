"""Migration verification test.

Creates a clean SQLite database in a temp directory, runs all Alembic
migrations programmatically, and verifies that all key tables exist.

Some migrations (003) use ``op.add_column`` with inline ``ForeignKey`` and
``op.drop_constraint`` / ``op.create_unique_constraint``, which SQLite does
not support via ALTER.  The custom ``env.py`` written into the temp directory
monkey-patches ``SQLiteImpl`` to allow these operations as no-ops / simple
executes, since SQLite ignores FK constraints by default and unique
constraints are rebuilt via the column specification.
"""

from __future__ import annotations

import os
import shutil
import textwrap

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(__file__))


def _make_config(tmp_path, db_path_name: str) -> tuple[Config, str]:
    """Build an alembic Config with a custom env.py for SQLite compatibility.

    Returns (Config, sync_db_url).
    """
    project_root = _project_root()
    source_versions = os.path.join(project_root, "alembic", "versions")
    db_path = os.path.join(str(tmp_path), db_path_name)
    db_url_sync = f"sqlite:///{db_path}"

    # Create the empty database file
    engine = create_engine(db_url_sync)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    engine.dispose()

    # Build a temporary alembic directory with a modified env.py
    alembic_dir = os.path.join(str(tmp_path), f"alembic_{db_path_name}")
    versions_dir = os.path.join(alembic_dir, "versions")
    os.makedirs(versions_dir, exist_ok=True)

    # Copy all version .py files (skip __pycache__ etc.)
    for fname in os.listdir(source_versions):
        if not fname.endswith(".py"):
            continue
        src = os.path.join(source_versions, fname)
        dst = os.path.join(versions_dir, fname)
        shutil.copy2(src, dst)

    # Write a custom env.py that:
    #   1. Uses a synchronous engine (no asyncio.run nesting issues)
    #   2. Patches SQLiteImpl to tolerate add_constraint / drop_constraint
    env_py = textwrap.dedent("""\
        from alembic import context
        from alembic.ddl.sqlite import SQLiteImpl
        from sqlalchemy import engine_from_config, pool

        from ai_benchmark.models import discovery, events, research, sources  # noqa: F401
        from ai_benchmark.models.base import Base

        config = context.config
        target_metadata = Base.metadata

        # SQLite does not support ALTER TABLE ... ADD CONSTRAINT or
        # DROP CONSTRAINT.  Patch the impl so that hand-written migrations
        # that use op.add_column with inline ForeignKey or op.drop_constraint
        # do not raise.
        _orig_add = SQLiteImpl.add_constraint
        _orig_drop = SQLiteImpl.drop_constraint

        def _lenient_add(self, const, **kw):
            try:
                _orig_add(self, const, **kw)
            except NotImplementedError:
                pass  # FK constraints are advisory on SQLite

        def _lenient_drop(self, const):
            try:
                _orig_drop(self, const)
            except NotImplementedError:
                pass  # dropping constraints is a no-op on SQLite

        SQLiteImpl.add_constraint = _lenient_add
        SQLiteImpl.drop_constraint = _lenient_drop


        def run_migrations_online():
            connectable = engine_from_config(
                config.get_section(config.config_ini_section),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )
            with connectable.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    render_as_batch=True,
                )
                with context.begin_transaction():
                    context.run_migrations()


        if context.is_offline_mode():
            url = config.get_main_option("sqlalchemy.url")
            context.configure(
                url=url,
                target_metadata=target_metadata,
                literal_binds=True,
                render_as_batch=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        else:
            run_migrations_online()
    """)
    with open(os.path.join(alembic_dir, "env.py"), "w") as f:
        f.write(env_py)

    # Create Config pointing at the temp alembic dir
    cfg = Config()
    cfg.set_main_option("script_location", alembic_dir)
    cfg.set_main_option("sqlalchemy.url", db_url_sync)

    return cfg, db_url_sync


# ── Expected table lists ──

CORE_TABLES = [
    "sources",
    "pages",
    "snapshots",
    "event_records",
    "claim_records",
    "cross_references",
    "candidate_papers",
    "enriched_papers",
]

DISCOVERY_TABLES = [
    "follow_up_tasks",
]


class TestMigrationChain:
    """Verify the full Alembic migration chain applies cleanly."""

    def test_upgrade_head_creates_all_tables(self, tmp_path):
        """Run all migrations and verify key tables exist."""
        cfg, db_url = _make_config(tmp_path, "all_tables.db")
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        engine.dispose()

        assert "alembic_version" in tables

        for table in CORE_TABLES:
            assert table in tables, f"Missing core table: {table}"

        for table in DISCOVERY_TABLES:
            assert table in tables, f"Missing discovery table: {table}"

    def test_upgrade_head_idempotent(self, tmp_path):
        """Running upgrade twice does not raise."""
        cfg, db_url = _make_config(tmp_path, "idempotent.db")

        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        engine.dispose()

        assert "sources" in tables

    def test_alembic_version_at_head(self, tmp_path):
        """After upgrade the alembic_version row contains revision 008."""
        cfg, db_url = _make_config(tmp_path, "version.db")
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            rows = result.fetchall()
        engine.dispose()

        assert len(rows) == 1
        assert rows[0][0] == "008"

    def test_core_tables_have_expected_columns(self, tmp_path):
        """Spot-check columns on sources and event_records."""
        cfg, db_url = _make_config(tmp_path, "columns.db")
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)

        source_cols = {c["name"] for c in inspector.get_columns("sources")}
        assert "id" in source_cols
        assert "source_name" in source_cols
        assert "trust_rating" in source_cols

        event_cols = {c["name"] for c in inspector.get_columns("event_records")}
        assert "id" in event_cols
        assert "title" in event_cols
        assert "source_id" in event_cols
        # Column added by migration 003
        assert "benchmark_variant" in event_cols

        engine.dispose()
