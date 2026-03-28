"""Tests for run API endpoints."""

from __future__ import annotations

import pytest


async def _setup_run_chain(client):
    """Create the full chain needed for a run: eval + dataset + target."""
    ds = await client.post("/api/eval/datasets", json={"name": "run-ds"})
    ds_id = ds.json()["id"]

    dv = await client.post(f"/api/eval/datasets/{ds_id}/versions", json={
        "items": [
            {"input_text": "Q1", "expected_output": "A1"},
            {"input_text": "Q2", "expected_output": "A2"},
        ],
    })
    dv_id = dv.json()["id"]

    ev_resp = await client.post("/api/eval/evaluations", json={"name": "run-eval"})
    eval_id = ev_resp.json()["id"]

    ev_ver = await client.post(f"/api/eval/evaluations/{eval_id}/versions", json={
        "dataset_version_id": dv_id,
        "scorer_config": [],
    })
    ev_ver_id = ev_ver.json()["id"]

    target = await client.post("/api/eval/targets", json={
        "name": "run-target",
        "model_name": "gpt-4o",
        "provider": "openai",
        "inference_params": {"temperature": 0.0},
    })
    target_id = target.json()["id"]

    return ev_ver_id, target_id


class TestRunsAPI:
    @pytest.mark.asyncio
    async def test_create_run(self, app_client):
        ev_ver_id, target_id = await _setup_run_chain(app_client)
        resp = await app_client.post("/api/eval/runs", json={
            "evaluation_version_id": ev_ver_id,
            "target_config_id": target_id,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "queued"
        assert data["total_items"] == 2

    @pytest.mark.asyncio
    async def test_get_run(self, app_client):
        ev_ver_id, target_id = await _setup_run_chain(app_client)
        create = await app_client.post("/api/eval/runs", json={
            "evaluation_version_id": ev_ver_id,
            "target_config_id": target_id,
        })
        run_id = create.json()["id"]
        resp = await app_client.get(f"/api/eval/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == run_id

    @pytest.mark.asyncio
    async def test_get_run_404(self, app_client):
        resp = await app_client.get("/api/eval/runs/9999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_run(self, app_client):
        ev_ver_id, target_id = await _setup_run_chain(app_client)
        create = await app_client.post("/api/eval/runs", json={
            "evaluation_version_id": ev_ver_id,
            "target_config_id": target_id,
        })
        run_id = create.json()["id"]
        resp = await app_client.post(f"/api/eval/runs/{run_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_list_runs(self, app_client):
        ev_ver_id, target_id = await _setup_run_chain(app_client)
        await app_client.post("/api/eval/runs", json={
            "evaluation_version_id": ev_ver_id,
            "target_config_id": target_id,
        })
        resp = await app_client.get("/api/eval/runs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_retry_run(self, app_client):
        ev_ver_id, target_id = await _setup_run_chain(app_client)
        create = await app_client.post("/api/eval/runs", json={
            "evaluation_version_id": ev_ver_id,
            "target_config_id": target_id,
        })
        run_id = create.json()["id"]
        resp = await app_client.post(f"/api/eval/runs/{run_id}/retry")
        assert resp.status_code == 201
        assert resp.json()["trigger_type"] == "retry"
        assert resp.json()["id"] != run_id


class TestComparisonsAPI:
    @pytest.mark.asyncio
    async def test_compare_requires_two_runs(self, app_client):
        resp = await app_client.post("/api/eval/comparisons/compare", json={
            "run_ids": [1],
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_config_diff_requires_two_targets(self, app_client):
        resp = await app_client.post("/api/eval/comparisons/config-diff", json={
            "target_ids": [1],
        })
        assert resp.status_code == 400
