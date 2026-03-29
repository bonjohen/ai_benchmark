"""Tests for evaluation API endpoints."""

from __future__ import annotations

import pytest


class TestEvaluationsAPI:
    @pytest.mark.asyncio
    async def test_create_evaluation(self, app_client):
        resp = await app_client.post(
            "/api/eval/evaluations",
            json={
                "name": "test-eval",
                "description": "A test evaluation",
                "execution_mode": "sequential",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-eval"
        assert data["id"] == 1

    @pytest.mark.asyncio
    async def test_list_evaluations(self, app_client):
        await app_client.post("/api/eval/evaluations", json={"name": "eval-1"})
        await app_client.post("/api/eval/evaluations", json={"name": "eval-2"})
        resp = await app_client.get("/api/eval/evaluations")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_get_evaluation(self, app_client):
        create = await app_client.post("/api/eval/evaluations", json={"name": "get-eval"})
        eval_id = create.json()["id"]
        resp = await app_client.get(f"/api/eval/evaluations/{eval_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-eval"

    @pytest.mark.asyncio
    async def test_get_evaluation_404(self, app_client):
        resp = await app_client.get("/api/eval/evaluations/9999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_evaluation(self, app_client):
        create = await app_client.post("/api/eval/evaluations", json={"name": "upd-eval"})
        eval_id = create.json()["id"]
        resp = await app_client.put(
            f"/api/eval/evaluations/{eval_id}",
            json={
                "description": "Updated description",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_create_version(self, app_client):
        # Create eval + dataset chain
        eval_resp = await app_client.post("/api/eval/evaluations", json={"name": "ver-eval"})
        eval_id = eval_resp.json()["id"]

        ds_resp = await app_client.post("/api/eval/datasets", json={"name": "ver-ds"})
        ds_id = ds_resp.json()["id"]

        dv_resp = await app_client.post(
            f"/api/eval/datasets/{ds_id}/versions",
            json={
                "items": [{"input_text": "Q1", "expected_output": "A1"}],
            },
        )
        dv_id = dv_resp.json()["id"]

        resp = await app_client.post(
            f"/api/eval/evaluations/{eval_id}/versions",
            json={
                "dataset_version_id": dv_id,
                "scorer_config": [{"scorer_version_id": 1, "weight": 1.0}],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["version_number"] == 1

    @pytest.mark.asyncio
    async def test_get_version(self, app_client):
        eval_resp = await app_client.post("/api/eval/evaluations", json={"name": "gv-eval"})
        eval_id = eval_resp.json()["id"]

        ds_resp = await app_client.post("/api/eval/datasets", json={"name": "gv-ds"})
        ds_id = ds_resp.json()["id"]

        dv_resp = await app_client.post(
            f"/api/eval/datasets/{ds_id}/versions",
            json={
                "items": [{"input_text": "Q"}],
            },
        )
        dv_id = dv_resp.json()["id"]

        await app_client.post(
            f"/api/eval/evaluations/{eval_id}/versions",
            json={
                "dataset_version_id": dv_id,
                "scorer_config": [],
            },
        )

        resp = await app_client.get(f"/api/eval/evaluations/{eval_id}/versions/1")
        assert resp.status_code == 200
        assert resp.json()["version_number"] == 1
