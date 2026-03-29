"""Tests for Phase 7: Runner adapters and execution integrations."""

from __future__ import annotations

import pytest

from ai_benchmark.eval.execution.adapters.base import (
    AdapterCapabilities,
    GenerationResult,
    RuntimeMetadata,
    resolve_adapter,
)

# --- Adapter registration ---


class TestAdapterRegistry:
    def test_all_eight_runners_registered(self):
        providers = [
            "ollama",
            "lmstudio",
            "llamacpp",
            "mlx",
            "vllm",
            "sglang",
            "tensorrt",
            "openvino",
        ]
        for provider in providers:
            adapter = resolve_adapter(provider)
            assert adapter is not None

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="No adapter"):
            resolve_adapter("nonexistent")


# --- Adapter interface ---


class TestAdapterInterface:
    @pytest.mark.parametrize(
        "provider",
        [
            "ollama",
            "lmstudio",
            "llamacpp",
            "mlx",
            "vllm",
            "sglang",
            "tensorrt",
            "openvino",
        ],
    )
    def test_adapter_has_generate(self, provider):
        adapter = resolve_adapter(provider)
        assert hasattr(adapter, "generate")
        assert callable(adapter.generate)

    @pytest.mark.parametrize(
        "provider",
        [
            "ollama",
            "lmstudio",
            "llamacpp",
            "mlx",
            "vllm",
            "sglang",
            "tensorrt",
            "openvino",
        ],
    )
    def test_adapter_has_health_check(self, provider):
        adapter = resolve_adapter(provider)
        assert hasattr(adapter, "health_check")

    @pytest.mark.parametrize(
        "provider",
        [
            "ollama",
            "lmstudio",
            "llamacpp",
            "mlx",
            "vllm",
            "sglang",
            "tensorrt",
            "openvino",
        ],
    )
    def test_adapter_has_capabilities(self, provider):
        adapter = resolve_adapter(provider)
        caps = adapter.capabilities()
        assert isinstance(caps, AdapterCapabilities)

    @pytest.mark.parametrize(
        "provider",
        [
            "ollama",
            "lmstudio",
            "llamacpp",
            "mlx",
            "vllm",
            "sglang",
            "tensorrt",
            "openvino",
        ],
    )
    def test_adapter_has_runtime_metadata(self, provider):
        adapter = resolve_adapter(provider)
        meta = adapter.get_runtime_metadata()
        assert isinstance(meta, RuntimeMetadata)
        assert meta.adapter_class != ""


# --- Default endpoints ---


class TestDefaultEndpoints:
    def test_ollama_default_endpoint(self):
        adapter = resolve_adapter("ollama")
        assert adapter.endpoint_url == "http://localhost:11434"

    def test_lmstudio_default_endpoint(self):
        adapter = resolve_adapter("lmstudio")
        assert adapter.endpoint_url == "http://localhost:1234"

    def test_llamacpp_default_endpoint(self):
        adapter = resolve_adapter("llamacpp")
        assert adapter.endpoint_url == "http://localhost:8080"

    def test_mlx_default_endpoint(self):
        adapter = resolve_adapter("mlx")
        assert adapter.endpoint_url == "http://localhost:8080"

    def test_vllm_default_endpoint(self):
        adapter = resolve_adapter("vllm")
        assert adapter.endpoint_url == "http://localhost:8000"

    def test_sglang_default_endpoint(self):
        adapter = resolve_adapter("sglang")
        assert adapter.endpoint_url == "http://localhost:30000"


# --- Capabilities ---


class TestCapabilities:
    def test_ollama_has_vision_and_tools(self):
        caps = resolve_adapter("ollama").capabilities()
        assert caps.vision
        assert caps.tool_use
        assert caps.streaming

    def test_mlx_minimal_capabilities(self):
        caps = resolve_adapter("mlx").capabilities()
        assert caps.streaming
        assert not caps.batch
        assert not caps.vision

    def test_vllm_has_batch(self):
        caps = resolve_adapter("vllm").capabilities()
        assert caps.batch
        assert caps.tool_use

    def test_sglang_has_batch(self):
        caps = resolve_adapter("sglang").capabilities()
        assert caps.batch


# --- Custom endpoint ---


class TestCustomEndpoint:
    def test_override_endpoint(self):
        adapter = resolve_adapter("ollama", endpoint_url="http://custom:9999")
        assert adapter.endpoint_url == "http://custom:9999"

    def test_override_model_name(self):
        adapter = resolve_adapter("vllm", model_name="llama3-70b")
        assert adapter.model_name == "llama3-70b"


# --- Runtime metadata ---


class TestRuntimeMetadata:
    def test_ollama_metadata(self):
        adapter = resolve_adapter("ollama", model_name="llama3-8b")
        meta = adapter.get_runtime_metadata()
        assert meta.adapter_class == "OllamaAdapter"
        assert meta.model_loaded == "llama3-8b"
        assert meta.extra["runner_name"] == "ollama"

    def test_vllm_metadata(self):
        adapter = resolve_adapter("vllm", endpoint_url="http://gpu:8000", model_name="phi-3")
        meta = adapter.get_runtime_metadata()
        assert meta.adapter_class == "VLLMAdapter"
        assert meta.endpoint_url == "http://gpu:8000"
        assert meta.extra["runner_name"] == "vllm"


# --- GenerationResult ---


class TestGenerationResult:
    def test_result_fields(self):
        r = GenerationResult(
            output_text="hello",
            latency_ms=42.5,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
        assert r.output_text == "hello"
        assert r.latency_ms == 42.5
        assert r.total_tokens == 15
        assert r.error is None

    def test_result_with_error(self):
        r = GenerationResult(output_text="", error="Connection refused")
        assert r.error == "Connection refused"
