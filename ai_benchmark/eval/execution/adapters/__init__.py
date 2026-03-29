"""Model adapter implementations — import all to populate the registry."""

from . import (  # noqa: F401
    anthropic_adapter,
    generic_http_adapter,
    llamacpp_adapter,
    lmstudio_adapter,
    local_adapter,
    mlx_adapter,
    ollama_adapter,
    openai_adapter,
    openvino_adapter,
    sglang_adapter,
    tensorrt_adapter,
    vllm_adapter,
)
