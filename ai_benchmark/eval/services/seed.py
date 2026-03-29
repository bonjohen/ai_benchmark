"""Seed initial runner and machine profiles for the lab environment."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..models.machine import MachineProfile
from ..models.runner import RunnerProfile

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

RUNNER_SEEDS: list[dict] = [
    {
        "name": "ollama-default",
        "runner_class": "ollama",
        "display_name": "Ollama",
        "version": "0.5.4",
        "default_endpoint_url": "http://localhost:11434/v1/chat/completions",
        "supported_machine_classes": [
            "dgx_spark",
            "apple_silicon_pro",
            "apple_silicon_mini",
            "rtx_desktop",
            "intel_ai_laptop",
            "old_gpu_laptop",
        ],
        "supported_model_families": ["llama", "gemma", "phi", "qwen", "mistral", "deepseek"],
        "parameter_surface": {
            "temperature": "float",
            "top_p": "float",
            "top_k": "int",
            "num_predict": "int",
            "num_ctx": "int",
            "num_gpu": "int",
            "repeat_penalty": "float",
        },
        "notes": "Cross-platform baseline runner. Easiest to install.",
    },
    {
        "name": "lmstudio-default",
        "runner_class": "lmstudio",
        "display_name": "LM Studio",
        "version": "0.3.8",
        "default_endpoint_url": "http://localhost:1234/v1/chat/completions",
        "supported_machine_classes": [
            "dgx_spark",
            "apple_silicon_pro",
            "apple_silicon_mini",
            "rtx_desktop",
            "intel_ai_laptop",
            "old_gpu_laptop",
        ],
        "supported_model_families": ["llama", "gemma", "phi", "qwen", "mistral", "deepseek"],
        "parameter_surface": {
            "temperature": "float",
            "max_tokens": "int",
            "top_p": "float",
            "top_k": "int",
        },
        "notes": "Desktop GUI runner with OpenAI-compatible API.",
    },
    {
        "name": "llamacpp-default",
        "runner_class": "llamacpp",
        "display_name": "llama.cpp",
        "version": "b4547",
        "default_endpoint_url": "http://localhost:8080/v1/chat/completions",
        "supported_machine_classes": [
            "dgx_spark",
            "apple_silicon_pro",
            "apple_silicon_mini",
            "rtx_desktop",
            "intel_ai_laptop",
            "old_gpu_laptop",
            "edge_device",
        ],
        "supported_model_families": ["llama", "gemma", "phi", "qwen", "mistral", "deepseek"],
        "parameter_surface": {
            "temperature": "float",
            "top_p": "float",
            "top_k": "int",
            "n_predict": "int",
            "n_ctx": "int",
            "n_gpu_layers": "int",
            "repeat_penalty": "float",
            "threads": "int",
        },
        "notes": "Portable low-level reference runner. Runs everywhere including edge devices.",
    },
    {
        "name": "mlx-default",
        "runner_class": "mlx",
        "display_name": "MLX / MLX-LM",
        "version": "0.21.0",
        "default_endpoint_url": "http://localhost:8080/v1/chat/completions",
        "supported_machine_classes": [
            "apple_silicon_pro",
            "apple_silicon_mini",
        ],
        "supported_model_families": ["llama", "gemma", "phi", "qwen", "mistral"],
        "parameter_surface": {
            "temperature": "float",
            "top_p": "float",
            "max_tokens": "int",
            "repetition_penalty": "float",
        },
        "notes": "Apple-native runner. Metal acceleration only — Apple Silicon required.",
    },
    {
        "name": "vllm-default",
        "runner_class": "vllm",
        "display_name": "vLLM",
        "version": "0.6.6",
        "default_endpoint_url": "http://localhost:8000/v1/chat/completions",
        "supported_machine_classes": [
            "dgx_spark",
            "rtx_desktop",
        ],
        "supported_model_families": ["llama", "gemma", "phi", "qwen", "mistral", "deepseek"],
        "parameter_surface": {
            "temperature": "float",
            "top_p": "float",
            "max_tokens": "int",
            "top_k": "int",
            "tensor_parallel_size": "int",
            "gpu_memory_utilization": "float",
        },
        "notes": "Server-style throughput runner. Requires NVIDIA GPU with CUDA.",
    },
    {
        "name": "sglang-default",
        "runner_class": "sglang",
        "display_name": "SGLang",
        "version": "0.4.3",
        "default_endpoint_url": "http://localhost:30000/v1/chat/completions",
        "supported_machine_classes": [
            "dgx_spark",
            "rtx_desktop",
        ],
        "supported_model_families": ["llama", "gemma", "qwen", "mistral", "deepseek"],
        "parameter_surface": {
            "temperature": "float",
            "top_p": "float",
            "max_new_tokens": "int",
            "top_k": "int",
            "tensor_parallel_size": "int",
        },
        "notes": "High-performance serving runner with RadixAttention. Requires NVIDIA GPU.",
    },
    {
        "name": "tensorrt-default",
        "runner_class": "tensorrt",
        "display_name": "TensorRT-LLM",
        "version": "0.16.0",
        "default_endpoint_url": "http://localhost:8000/v1/chat/completions",
        "supported_machine_classes": [
            "dgx_spark",
            "rtx_desktop",
        ],
        "supported_model_families": ["llama", "gemma", "phi", "qwen", "mistral"],
        "parameter_surface": {
            "temperature": "float",
            "top_p": "float",
            "max_tokens": "int",
            "top_k": "int",
            "max_batch_size": "int",
        },
        "notes": "NVIDIA-native optimized runner. Requires engine build step before serving.",
    },
    {
        "name": "openvino-default",
        "runner_class": "openvino",
        "display_name": "OpenVINO GenAI",
        "version": "2025.0",
        "default_endpoint_url": "http://localhost:8000/v1/chat/completions",
        "supported_machine_classes": [
            "intel_ai_laptop",
        ],
        "supported_model_families": ["llama", "gemma", "phi", "qwen"],
        "parameter_surface": {
            "temperature": "float",
            "top_p": "float",
            "max_new_tokens": "int",
            "top_k": "int",
        },
        "notes": "Intel AI hardware runner. NPU acceleration on supported Intel Core Ultra CPUs.",
    },
]

MACHINE_SEEDS: list[dict] = [
    {
        "hostname": "dgx-spark-01",
        "display_name": "NVIDIA DGX Spark",
        "hardware_class": "dgx_spark",
        "cpu_description": "NVIDIA Grace (72 Arm cores)",
        "gpu_description": "NVIDIA Blackwell GPU, 128 GB unified",
        "accelerator_details": {
            "type": "nvidia_blackwell",
            "memory_gb": 128,
            "unified_memory": True,
            "compute_capability": "10.0",
        },
        "ram_gb": 128,
        "storage_summary": "4 TB NVMe SSD",
        "os_description": "Ubuntu 22.04 LTS (DGX OS)",
        "runtime_availability": [
            "ollama",
            "lmstudio",
            "llamacpp",
            "vllm",
            "sglang",
            "tensorrt",
        ],
        "capacity_notes": "Primary high-capability environment. Supports all CUDA runners.",
    },
    {
        "hostname": "mbp-m4-64",
        "display_name": "MacBook Pro M4 64 GB",
        "hardware_class": "apple_silicon_pro",
        "cpu_description": "Apple M4 Pro (14-core)",
        "gpu_description": "Apple M4 Pro (20-core GPU), 64 GB unified",
        "accelerator_details": {
            "type": "apple_silicon",
            "chip": "M4 Pro",
            "gpu_cores": 20,
            "neural_engine_cores": 16,
            "memory_gb": 64,
            "unified_memory": True,
        },
        "ram_gb": 64,
        "storage_summary": "2 TB NVMe SSD",
        "os_description": "macOS Sequoia 15.3",
        "runtime_availability": ["ollama", "lmstudio", "llamacpp", "mlx"],
        "capacity_notes": "Apple Silicon pro workstation. Best for MLX benchmarks.",
    },
    {
        "hostname": "mac-mini-m4-24",
        "display_name": "Mac mini M4 24 GB",
        "hardware_class": "apple_silicon_mini",
        "cpu_description": "Apple M4 (10-core)",
        "gpu_description": "Apple M4 (10-core GPU), 24 GB unified",
        "accelerator_details": {
            "type": "apple_silicon",
            "chip": "M4",
            "gpu_cores": 10,
            "neural_engine_cores": 16,
            "memory_gb": 24,
            "unified_memory": True,
        },
        "ram_gb": 24,
        "storage_summary": "512 GB NVMe SSD",
        "os_description": "macOS Sequoia 15.3",
        "runtime_availability": ["ollama", "lmstudio", "llamacpp", "mlx"],
        "capacity_notes": "Entry-level Apple Silicon. Tests VRAM-constrained scenarios.",
    },
    {
        "hostname": "rtx4070-desktop",
        "display_name": "RTX 4070 Desktop",
        "hardware_class": "rtx_desktop",
        "cpu_description": "AMD Ryzen 7 7800X3D (8-core)",
        "gpu_description": "NVIDIA RTX 4070 12 GB GDDR6X",
        "accelerator_details": {
            "type": "nvidia_rtx",
            "model": "RTX 4070",
            "vram_gb": 12,
            "compute_capability": "8.9",
            "cuda_cores": 5888,
        },
        "ram_gb": 32,
        "storage_summary": "1 TB NVMe SSD",
        "os_description": "Ubuntu 24.04 LTS",
        "runtime_availability": [
            "ollama",
            "lmstudio",
            "llamacpp",
            "vllm",
            "sglang",
            "tensorrt",
        ],
        "capacity_notes": "Mid-range NVIDIA desktop. 12 GB VRAM limits model sizes.",
    },
    {
        "hostname": "vivobook-s15",
        "display_name": "ASUS Vivobook S 15",
        "hardware_class": "intel_ai_laptop",
        "cpu_description": "Intel Core Ultra 7 155H (16-core, NPU)",
        "gpu_description": "Intel Arc integrated GPU",
        "accelerator_details": {
            "type": "intel_npu",
            "npu_tops": 11,
            "cpu_threads": 22,
            "integrated_gpu": "Intel Arc",
        },
        "ram_gb": 32,
        "storage_summary": "1 TB NVMe SSD",
        "os_description": "Windows 11 Pro",
        "runtime_availability": ["ollama", "lmstudio", "llamacpp", "openvino"],
        "capacity_notes": "Intel AI laptop with NPU. Primary OpenVINO test target.",
    },
    {
        "hostname": "gtx1060-laptop",
        "display_name": "GTX 1060 6G Laptop",
        "hardware_class": "old_gpu_laptop",
        "cpu_description": "Intel Core i7-7700HQ (4-core)",
        "gpu_description": "NVIDIA GTX 1060 6 GB GDDR5",
        "accelerator_details": {
            "type": "nvidia_legacy",
            "model": "GTX 1060",
            "vram_gb": 6,
            "compute_capability": "6.1",
            "cuda_cores": 1280,
        },
        "ram_gb": 16,
        "storage_summary": "512 GB SATA SSD",
        "os_description": "Ubuntu 22.04 LTS",
        "runtime_availability": ["ollama", "lmstudio", "llamacpp"],
        "capacity_notes": "Legacy GPU. Backlog — tests old-hardware degradation.",
    },
    {
        "hostname": "rpi-edge-01",
        "display_name": "Raspberry Pi Edge",
        "hardware_class": "edge_device",
        "cpu_description": "Broadcom BCM2712 (4-core Arm Cortex-A76)",
        "gpu_description": "VideoCore VII (no CUDA)",
        "accelerator_details": {
            "type": "edge",
            "model": "Raspberry Pi 5",
            "accelerator_hat": "Hailo-8L (planned)",
        },
        "ram_gb": 8,
        "storage_summary": "128 GB microSD",
        "os_description": "Raspberry Pi OS (Debian 12 Bookworm)",
        "runtime_availability": ["llamacpp"],
        "capacity_notes": "Edge device. Backlog — tests extreme resource constraints.",
    },
]


async def seed_runners(session: AsyncSession) -> list[RunnerProfile]:
    """Seed all 8 runner profiles. Skips runners that already exist by name."""
    created = []
    for data in RUNNER_SEEDS:
        from sqlalchemy import select

        existing = await session.execute(
            select(RunnerProfile).where(RunnerProfile.name == data["name"])
        )
        if existing.scalar_one_or_none() is not None:
            continue
        runner = RunnerProfile(
            name=data["name"],
            runner_class=data["runner_class"],
            display_name=data.get("display_name"),
            version=data.get("version"),
            default_endpoint_url=data.get("default_endpoint_url"),
            supported_machine_classes=json.dumps(data["supported_machine_classes"]),
            supported_model_families=json.dumps(data["supported_model_families"]),
            parameter_surface=json.dumps(data["parameter_surface"]),
            notes=data.get("notes"),
        )
        session.add(runner)
        created.append(runner)
    await session.flush()
    return created


async def seed_machines(session: AsyncSession) -> list[MachineProfile]:
    """Seed all 7 machine profiles. Skips machines that already exist by hostname."""
    created = []
    for data in MACHINE_SEEDS:
        from sqlalchemy import select

        existing = await session.execute(
            select(MachineProfile).where(MachineProfile.hostname == data["hostname"])
        )
        if existing.scalar_one_or_none() is not None:
            continue
        machine = MachineProfile(
            hostname=data["hostname"],
            display_name=data.get("display_name"),
            hardware_class=data["hardware_class"],
            cpu_description=data.get("cpu_description"),
            gpu_description=data.get("gpu_description"),
            accelerator_details=json.dumps(data["accelerator_details"])
            if data.get("accelerator_details")
            else None,
            ram_gb=data.get("ram_gb"),
            storage_summary=data.get("storage_summary"),
            os_description=data.get("os_description"),
            runtime_availability=json.dumps(data["runtime_availability"])
            if data.get("runtime_availability")
            else None,
            capacity_notes=data.get("capacity_notes"),
        )
        session.add(machine)
        created.append(machine)
    await session.flush()
    return created


async def seed_all(session: AsyncSession) -> dict[str, int]:
    """Seed all runner and machine profiles. Returns counts of created records."""
    runners = await seed_runners(session)
    machines = await seed_machines(session)
    return {"runners": len(runners), "machines": len(machines)}
