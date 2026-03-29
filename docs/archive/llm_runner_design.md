1. **Ollama** should be treated as the **baseline cross-platform runner** in your lab, not merely the convenient one. It runs on macOS, Windows, and Linux, exposes a local API by default at `localhost:11434`, and is suitable for giving you one common execution surface across the DGX Spark, Apple Silicon systems, the RTX 4070 desktop, and the Vivobook. In your evaluation pipeline, its value is that it reduces runner variance and gives you a stable “general-purpose host” against which more specialized runners can be compared. ([Ollama Documentation][1])

2. **LM Studio** should be treated as the **interactive workstation runner**. It supports macOS, Windows, and Linux, can serve local models on OpenAI-like endpoints, and can run `llama.cpp` models broadly plus `MLX` models on Apple Silicon. In your evaluation framework, LM Studio is not just “easy to use”; it is the runner you use when you want to measure results in a desktop-oriented environment that combines model management, manual inspection, and API hosting. ([LM Studio][2])

3. **llama.cpp** should be treated as the **portable low-level reference runner**. Its official repository lists broad backend support including Metal for Apple Silicon, CUDA for NVIDIA GPUs, and SYCL for Intel and NVIDIA GPUs. In your lab, this makes it the most important runner for isolating hardware behavior, because it is the one most likely to run across your Macs, RTX 4070, Vivobook-class Intel hardware, and older backlog systems like the GTX 1060 laptop. ([GitHub][3])

4. **MLX / MLX-LM** should be treated as the **Apple-native runner**. Apple’s `mlx-lm` project is specifically for generating text and fine-tuning large language models on Apple Silicon with MLX. In your evaluation pipeline, this runner is not a convenience tool at all; it is the “Apple-specific optimization path” that should be compared directly against Ollama, LM Studio, and `llama.cpp` on the MacBook Pro M4 64 GB and the Mac mini 24 GB. ([GitHub][4])

5. **vLLM** should be treated as the **server-style throughput runner**. Its official docs center around an OpenAI-compatible HTTP server started with `vllm serve`. In your lab, it belongs in the matrix when the question is not merely “does the model run?” but “how does this configuration behave as a service endpoint under a more production-like runner?” That makes it especially relevant on the DGX Spark and the RTX 4070 desktop. ([vLLM][5])

6. **SGLang** should be treated as the **high-performance serving runner** for serious NVIDIA-side experiments. Its docs describe it as a high-performance serving framework for LLMs and multimodal models, and explicitly list NVIDIA Spark among supported hardware. In your evaluation system, SGLang is a major candidate runner for the DGX Spark because it tests what happens when you move from general-purpose local hosting to a runner designed around low-latency and high-throughput serving. ([SGLang Documentation][6])

7. **TensorRT-LLM** should be treated as the **NVIDIA-native optimized runner**. NVIDIA positions it as a library for building TensorRT engines and running optimized LLM inference on NVIDIA GPUs, with Python and C++ runtimes and a production API. In your lab, this is the runner to compare when the question is specifically “what is the best NVIDIA-aligned path for this model and hardware combination?” rather than “what is the simplest host?” ([NVIDIA Docs][7])

8. **OpenVINO GenAI** should be treated as the **Intel AI hardware runner**, especially for the ASUS Vivobook S 15 OLED with the Core Ultra 7 155H and built-in Intel AI Boost NPU. OpenVINO’s current docs explicitly describe LLM inference on NPU, including constraints and configuration around prompt and response length. In your evaluation matrix, OpenVINO is the runner that tells you whether the Vivobook’s dedicated AI hardware materially changes the outcome compared with CPU/GPU-oriented runners like Ollama or `llama.cpp`. ([OpenVINO Documentation][8])

## Comparison and contrast as evaluation components

The right framing for your lab is that the **runner is itself a test variable**. A model result is not just “model X on machine Y.” It is “model X with runner Z, backend configuration A, and machine profile B.” Ollama, LM Studio, `llama.cpp`, MLX, vLLM, SGLang, TensorRT-LLM, and OpenVINO should therefore be treated as competing execution layers whose differences may change speed, memory fit, compatibility, stability, and even output behavior under identical evaluation prompts. The runner belongs in the metadata and in the comparison UI just like quantization, context length, and temperature. ([Ollama Documentation][9])

A useful way to separate them is by **what they are optimizing for**. Ollama is a common API baseline. LM Studio is a desktop interactive runner. `llama.cpp` is the portable low-level reference. MLX is the Apple-native path. vLLM and SGLang are service-oriented runners. TensorRT-LLM is the NVIDIA-specific optimization path. OpenVINO GenAI is the Intel AI hardware path. These are not redundant products; they represent distinct experimental classes. Your pipeline should expose “runner class” as a first-class comparison dimension. ([Ollama Documentation][1])

## How they fit your hardware

On the **DGX Spark 128 GB**, the most meaningful runners to evaluate are **Ollama** as the common baseline, **vLLM** as a service-style runner, **SGLang** as a high-performance serving runner, and **TensorRT-LLM** as the NVIDIA-native optimized runner. That gives you four distinct execution philosophies on the same primary machine: common baseline, generic service engine, advanced serving framework, and NVIDIA-specific optimization path. ([Ollama Documentation][9])

On the **MacBook Pro M4 64 GB** and **Mac mini 24 GB**, the key runners are **Ollama**, **LM Studio**, **llama.cpp**, and **MLX / MLX-LM**. Here the central question is not just which model runs, but whether Apple-native execution through MLX changes quality, speed, memory behavior, or model fit compared with more general runners. LM Studio is also especially relevant because it can act as both a workstation interface and a local server while using `MLX` on Apple Silicon. ([LM Studio][2])

On the **RTX 4070 desktop**, the strongest runner matrix is **Ollama**, **llama.cpp**, **vLLM**, **SGLang**, and optionally **TensorRT-LLM**. That gives you a clean progression from general local runner to low-level runner to stronger server-oriented runners. On this machine, runner choice is likely to have a large practical effect on throughput, compatibility, and how “server-like” the box behaves. ([Ollama Documentation][9])

On the **ASUS Vivobook S 15 OLED**, the core matrix should be **Ollama**, **LM Studio**, **llama.cpp**, and **OpenVINO GenAI**. The first three tell you how a normal laptop behaves under general-purpose runners. OpenVINO tells you whether the Intel NPU path actually matters for the model and configuration you care about. That makes the Vivobook less of a generic laptop test and more of a “consumer AI PC hardware path” experiment. ([LM Studio][2])

For the **GTX 1060 6 GB backlog laptop**, the most important runner is **llama.cpp**, with **Ollama** as a secondary baseline. This is the old-hardware fit test. You are trying to determine not just whether a model runs, but whether a runner remains viable under tighter VRAM and older GPU constraints. `llama.cpp` is the most important reference because of its backend flexibility. ([GitHub][3])

For the **Raspberry Pi with NPU backlog**, the runner question depends on the accelerator class. In practical terms, this belongs in the lab as a separate edge-inference class rather than as a direct peer to your DGX Spark or RTX 4070 environments. The main lesson here is that edge-oriented accelerators often imply a different execution stack and should be modeled as a distinct runner/hardware category in the evaluation system. OpenVINO’s NPU-oriented constraints are a good example of why these paths need dedicated metadata rather than being hidden inside a generic “local model run.” ([OpenVINO Documentation][8])

## Summary: primary qualities and when to use them

Use **Ollama** when you want the **cross-platform baseline runner**. It is the control condition for the rest of the lab. ([Ollama Documentation][9])

Use **LM Studio** when you want the **desktop lab runner** that combines hosting, inspection, and workstation-style usage. ([LM Studio][10])

Use **llama.cpp** when you want the **portable reference runner** across the widest range of hardware. ([GitHub][3])

Use **MLX / MLX-LM** when you want the **Apple-native runner** and want to measure what Apple Silicon itself contributes. ([GitHub][4])

Use **vLLM** when you want the **generic service-style runner** for stronger GPU-backed API hosting. ([vLLM][11])

Use **SGLang** when you want the **advanced serving runner** for DGX Spark and other performance-oriented environments. ([SGLang Documentation][6])

Use **TensorRT-LLM** when you want the **NVIDIA-optimized runner** and the experiment is specifically about NVIDIA performance and deployment behavior. ([NVIDIA Developer][12])

Use **OpenVINO GenAI** when you want the **Intel AI hardware runner**, especially on the Vivobook and similar NPU-equipped systems. ([OpenVINO Documentation][8])

The simplest reframe is this: **your lab should evaluate model × machine × runner × configuration**, not just model × machine. That turns the runner from an implementation detail into a first-class experimental component.

[1]: https://docs.ollama.com/?utm_source=chatgpt.com "Ollama's documentation - Ollama"
[2]: https://lmstudio.ai/docs/?utm_source=chatgpt.com "Welcome to LM Studio Docs! | LM Studio Docs"
[3]: https://github.com/crc-org/llama.cpp/?utm_source=chatgpt.com "GitHub - crc-org/llama.cpp"
[4]: https://github.com/ml-explore/mlx-lm?utm_source=chatgpt.com "GitHub - ml-explore/mlx-lm: Run LLMs with MLX"
[5]: https://docs.vllm.ai/serving/openai_compatible_server.html?utm_source=chatgpt.com "OpenAI-Compatible Server - vLLM"
[6]: https://docs.sglang.io/?utm_source=chatgpt.com "SGLang Documentation — SGLang"
[7]: https://docs.nvidia.com/tensorrt-llm/?utm_source=chatgpt.com "NVIDIA TensorRT-LLM - NVIDIA Docs"
[8]: https://docs.openvino.ai/2026/openvino-workflow-generative/inference-with-genai/inference-with-genai-on-npu.html?utm_source=chatgpt.com "OpenVINO GenAI on NPU — OpenVINO™ documentation"
[9]: https://docs.ollama.com/api?utm_source=chatgpt.com "Introduction - Ollama"
[10]: https://lmstudio.ai/docs/developer/core/server?utm_source=chatgpt.com "LM Studio as a Local LLM API Server | LM Studio Docs"
[11]: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html?utm_source=chatgpt.com "OpenAI-Compatible Server - vLLM"
[12]: https://developer.nvidia.com/tensorrt-llm?utm_source=chatgpt.com "TensorRT LLM | NVIDIA Developer"
