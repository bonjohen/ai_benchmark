"""Phase 11 tests — Definition management UI: detail pages, workflows, preview."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from ai_benchmark.eval.api.app import create_app
from ai_benchmark.eval.config import EvalSettings
from ai_benchmark.eval.models.artifact import Artifact  # noqa: F401
from ai_benchmark.eval.models.dataset import Dataset, DatasetVersion, TestCase
from ai_benchmark.eval.models.evaluation import EvaluationDefinition, EvaluationVersion
from ai_benchmark.eval.models.machine import MachineProfile
from ai_benchmark.eval.models.runner import RunnerProfile  # noqa: F401
from ai_benchmark.eval.models.scorer import Scorer, ScorerVersion
from ai_benchmark.eval.models.target import TargetConfiguration
from ai_benchmark.models.base import create_session_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session(db_engine_fk) -> AsyncSession:
    session_factory = create_session_factory(db_engine_fk)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def ui_client(db_engine_fk):
    import ai_benchmark.eval.api.app as app_module

    settings = EvalSettings()
    app = create_app(settings)

    test_factory = create_session_factory(db_engine_fk)
    original = app_module._session_factory
    app_module._session_factory = test_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        yield client

    app_module._session_factory = original


# ── Evaluation Management ──


class TestEvaluationManagement:
    @pytest.mark.asyncio
    async def test_evaluation_detail_shows_archive_button(self, db_session, ui_client):
        ed = EvaluationDefinition(name="arch-test", execution_mode="sequential")
        db_session.add(ed)
        await db_session.flush()
        eid = ed.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/evaluations/{eid}")
        assert resp.status_code == 200
        assert "Archive" in resp.text

    @pytest.mark.asyncio
    async def test_evaluation_archive(self, db_session, ui_client):
        ed = EvaluationDefinition(name="to-archive", execution_mode="sequential")
        db_session.add(ed)
        await db_session.flush()
        eid = ed.id
        await db_session.commit()

        resp = await ui_client.post(f"/eval/evaluations/{eid}/archive")
        assert resp.status_code == 200  # Redirect followed
        assert "Archived" in resp.text

    @pytest.mark.asyncio
    async def test_evaluation_version_display(self, db_session, ui_client):
        ed = EvaluationDefinition(name="ver-test", execution_mode="sequential")
        db_session.add(ed)
        await db_session.flush()

        ds = Dataset(name="ver-ds", source="manual")
        db_session.add(ds)
        await db_session.flush()
        dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=5)
        db_session.add(dv)
        await db_session.flush()

        ev = EvaluationVersion(
            evaluation_id=ed.id,
            version_number=1,
            dataset_version_id=dv.id,
            scorer_config='[{"scorer": "exact_match"}]',
        )
        db_session.add(ev)
        await db_session.commit()

        resp = await ui_client.get(f"/eval/evaluations/{ed.id}")
        assert resp.status_code == 200
        assert "v1" in resp.text
        assert "exact_match" in resp.text


# ── Dataset Preview ──


class TestDatasetPreview:
    @pytest.mark.asyncio
    async def test_dataset_detail_has_preview_link(self, db_session, ui_client):
        ds = Dataset(name="prev-ds", source="manual")
        db_session.add(ds)
        await db_session.flush()
        dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=2)
        db_session.add(dv)
        await db_session.flush()
        dv_id = dv.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/datasets/{ds.id}")
        assert resp.status_code == 200
        assert "Preview" in resp.text
        assert f"/versions/{dv_id}/preview" in resp.text

    @pytest.mark.asyncio
    async def test_dataset_version_preview(self, db_session, ui_client):
        ds = Dataset(name="tc-prev", source="manual")
        db_session.add(ds)
        await db_session.flush()
        dv = DatasetVersion(dataset_id=ds.id, version_number=1, item_count=2)
        db_session.add(dv)
        await db_session.flush()

        tc1 = TestCase(
            dataset_version_id=dv.id,
            item_index=0,
            input_text="What is 2+2?",
            expected_output="4",
        )
        tc2 = TestCase(
            dataset_version_id=dv.id,
            item_index=1,
            input_text="Capital of France?",
            expected_output="Paris",
        )
        db_session.add_all([tc1, tc2])
        await db_session.commit()

        resp = await ui_client.get(f"/eval/datasets/{ds.id}/versions/{dv.id}/preview")
        assert resp.status_code == 200
        assert "What is 2+2?" in resp.text
        assert "Capital of France?" in resp.text
        assert "Test Cases" in resp.text

    @pytest.mark.asyncio
    async def test_dataset_version_preview_not_found(self, db_session, ui_client):
        ds = Dataset(name="nf-ds", source="manual")
        db_session.add(ds)
        await db_session.commit()

        resp = await ui_client.get(f"/eval/datasets/{ds.id}/versions/99999/preview")
        assert resp.status_code == 404


# ── Scorer Detail ──


class TestScorerDetail:
    @pytest.mark.asyncio
    async def test_scorer_list_links_to_detail(self, db_session, ui_client):
        scorer = Scorer(name="link-scorer", scorer_type="exact_match")
        db_session.add(scorer)
        await db_session.flush()
        sid = scorer.id
        await db_session.commit()

        resp = await ui_client.get("/eval/scorers")
        assert resp.status_code == 200
        assert f"/eval/scorers/{sid}" in resp.text

    @pytest.mark.asyncio
    async def test_scorer_detail_page(self, db_session, ui_client):
        scorer = Scorer(
            name="detail-scorer",
            scorer_type="fuzzy_match",
            description="Fuzzy string matching scorer",
        )
        db_session.add(scorer)
        await db_session.flush()
        sid = scorer.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/scorers/{sid}")
        assert resp.status_code == 200
        assert "detail-scorer" in resp.text
        assert "fuzzy_match" in resp.text
        assert "Fuzzy string matching scorer" in resp.text

    @pytest.mark.asyncio
    async def test_scorer_version_history(self, db_session, ui_client):
        scorer = Scorer(name="ver-scorer", scorer_type="rubric")
        db_session.add(scorer)
        await db_session.flush()

        sv = ScorerVersion(
            scorer_id=scorer.id,
            version_number=1,
            config='{"threshold": 0.8}',
            notes="Initial version",
        )
        db_session.add(sv)
        await db_session.commit()

        resp = await ui_client.get(f"/eval/scorers/{scorer.id}")
        assert resp.status_code == 200
        assert "v1" in resp.text
        assert "Initial version" in resp.text

    @pytest.mark.asyncio
    async def test_scorer_not_found(self, ui_client):
        resp = await ui_client.get("/eval/scorers/99999")
        assert resp.status_code == 404


# ── Machine Detail ──


class TestMachineDetail:
    @pytest.mark.asyncio
    async def test_machine_list_links_to_detail(self, db_session, ui_client):
        m = MachineProfile(hostname="link-host", hardware_class="dgx_spark")
        db_session.add(m)
        await db_session.flush()
        mid = m.id
        await db_session.commit()

        resp = await ui_client.get("/eval/machines")
        assert resp.status_code == 200
        assert f"/eval/machines/{mid}" in resp.text

    @pytest.mark.asyncio
    async def test_machine_detail_page(self, db_session, ui_client):
        m = MachineProfile(
            hostname="detail-host",
            display_name="DGX Test",
            hardware_class="dgx_spark",
            cpu_description="Grace 72-core",
            gpu_description="Blackwell B200",
            ram_gb=128,
            os_description="Ubuntu 24.04",
            capacity_notes="Primary inference machine",
        )
        db_session.add(m)
        await db_session.flush()
        mid = m.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/machines/{mid}")
        assert resp.status_code == 200
        assert "DGX Test" in resp.text
        assert "Grace 72-core" in resp.text
        assert "Blackwell B200" in resp.text
        assert "128" in resp.text
        assert "Primary inference machine" in resp.text

    @pytest.mark.asyncio
    async def test_machine_detail_with_runtime(self, db_session, ui_client):
        m = MachineProfile(
            hostname="rt-host",
            hardware_class="apple_silicon",
            runtime_availability=json.dumps(["ollama", "mlx", "llamacpp"]),
        )
        db_session.add(m)
        await db_session.flush()
        mid = m.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/machines/{mid}")
        assert resp.status_code == 200
        assert "ollama" in resp.text
        assert "mlx" in resp.text

    @pytest.mark.asyncio
    async def test_machine_not_found(self, ui_client):
        resp = await ui_client.get("/eval/machines/99999")
        assert resp.status_code == 404


# ── Target Clone ──


class TestTargetClone:
    @pytest.mark.asyncio
    async def test_target_detail_has_clone_button(self, db_session, ui_client):
        t = TargetConfiguration(
            name="clone-src",
            model_name="llama3",
            provider="ollama",
            inference_params="{}",
        )
        db_session.add(t)
        await db_session.flush()
        tid = t.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/targets/{tid}")
        assert resp.status_code == 200
        assert "Clone" in resp.text
        assert f"/eval/targets/{tid}/clone" in resp.text

    @pytest.mark.asyncio
    async def test_target_clone_form(self, db_session, ui_client):
        t = TargetConfiguration(
            name="clone-form-src",
            model_name="mistral",
            provider="vllm",
            inference_params="{}",
        )
        db_session.add(t)
        await db_session.flush()
        tid = t.id
        await db_session.commit()

        resp = await ui_client.get(f"/eval/targets/{tid}/clone")
        assert resp.status_code == 200
        assert "Clone Target" in resp.text
        assert "clone-form-src" in resp.text

    @pytest.mark.asyncio
    async def test_target_clone_submit(self, db_session, ui_client):
        t = TargetConfiguration(
            name="clone-submit-src",
            model_name="llama3",
            provider="ollama",
            inference_params='{"temperature": 0.7}',
        )
        db_session.add(t)
        await db_session.flush()
        tid = t.id
        await db_session.commit()

        resp = await ui_client.post(
            f"/eval/targets/{tid}/clone",
            data={"new_name": "cloned-target"},
        )
        assert resp.status_code == 200  # Redirect followed
        assert "cloned-target" in resp.text
