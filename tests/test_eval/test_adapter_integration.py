"""Integration tests for model adapters against mock HTTP servers.

Uses respx to intercept httpx requests made by the adapters, verifying
request construction, response parsing, and error handling.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from ai_benchmark.eval.execution.adapters.anthropic_adapter import AnthropicAdapter
from ai_benchmark.eval.execution.adapters.generic_http_adapter import GenericHTTPAdapter
from ai_benchmark.eval.execution.adapters.openai_adapter import OpenAIAdapter

# ── Helpers ──

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GENERIC_URL = "https://custom-model.example.com/generate"


def _openai_response(content: str = "Hello!", prompt_tokens: int = 10, completion_tokens: int = 5):
    """Build a realistic OpenAI chat completion response dict."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _anthropic_response(
    text: str = "Hi there!",
    input_tokens: int = 12,
    output_tokens: int = 8,
):
    """Build a realistic Anthropic messages API response dict."""
    return {
        "id": "msg_test456",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-20250514",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }


# ── OpenAI Adapter ──


class TestOpenAIAdapter:
    """Tests for OpenAIAdapter against mock HTTP server."""

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        """Adapter parses a normal chat completion response correctly."""
        adapter = OpenAIAdapter(
            endpoint_url=OPENAI_URL,
            api_key="sk-test-key",
            model_name="gpt-4o",
        )
        with respx.mock:
            respx.post(OPENAI_URL).mock(
                return_value=httpx.Response(200, json=_openai_response("The answer is 42."))
            )
            result = await adapter.generate("What is the answer?", {"temperature": 0.7})

        assert result.output_text == "The answer is 42."
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.total_tokens == 15
        assert result.latency_ms > 0
        assert result.error is None
        assert result.raw_response is not None
        assert result.raw_response["id"] == "chatcmpl-test123"

    @pytest.mark.asyncio
    async def test_successful_generation_with_system_prompt(self):
        """System prompt from runtime_options is included in request body."""
        adapter = OpenAIAdapter(
            endpoint_url=OPENAI_URL,
            api_key="sk-test-key",
        )
        captured_body = {}

        def capture_request(request):
            import json

            captured_body.update(json.loads(request.content))
            return httpx.Response(200, json=_openai_response())

        with respx.mock:
            respx.post(OPENAI_URL).mock(side_effect=capture_request)
            await adapter.generate(
                "Hello",
                {"temperature": 0.5},
                runtime_options={"system_prompt": "You are helpful."},
            )

        assert len(captured_body["messages"]) == 2
        assert captured_body["messages"][0]["role"] == "system"
        assert captured_body["messages"][0]["content"] == "You are helpful."
        assert captured_body["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_authorization_header_sent(self):
        """API key is sent as Bearer token in Authorization header."""
        adapter = OpenAIAdapter(
            endpoint_url=OPENAI_URL,
            api_key="sk-test-key",
        )
        captured_headers = {}

        def capture_request(request):
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json=_openai_response())

        with respx.mock:
            respx.post(OPENAI_URL).mock(side_effect=capture_request)
            await adapter.generate("Hi", {})

        assert captured_headers.get("authorization") == "Bearer sk-test-key"

    @pytest.mark.asyncio
    async def test_http_500_error(self):
        """Adapter captures HTTP 500 errors gracefully."""
        adapter = OpenAIAdapter(
            endpoint_url=OPENAI_URL,
            api_key="sk-test-key",
            model_name="gpt-4o",
        )
        with respx.mock:
            respx.post(OPENAI_URL).mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )
            result = await adapter.generate(
                "Hello",
                {"temperature": 0.5},
                runtime_options={"retries": 0},
            )

        assert result.output_text == ""
        assert result.error is not None
        assert "500" in result.error
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_rate_limit_retry_then_fail(self):
        """429 responses trigger retries; final 429 still returns an error."""
        adapter = OpenAIAdapter(
            endpoint_url=OPENAI_URL,
            api_key="sk-test-key",
        )
        call_count = 0

        def rate_limit_side_effect(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(429, text="Rate limited")

        with respx.mock:
            respx.post(OPENAI_URL).mock(side_effect=rate_limit_side_effect)
            result = await adapter.generate(
                "Hello",
                {},
                runtime_options={"retries": 2},
            )

        # 1 initial + 2 retries = 3 total attempts
        assert call_count == 3
        assert result.error is not None
        assert "429" in result.error
        assert result.retry_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_retry_then_success(self):
        """429 on first attempt, success on second."""
        adapter = OpenAIAdapter(
            endpoint_url=OPENAI_URL,
            api_key="sk-test-key",
        )
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429, text="Rate limited")
            return httpx.Response(200, json=_openai_response("Recovered!"))

        with respx.mock:
            respx.post(OPENAI_URL).mock(side_effect=side_effect)
            result = await adapter.generate(
                "Hello",
                {},
                runtime_options={"retries": 2},
            )

        assert call_count == 2
        assert result.output_text == "Recovered!"
        assert result.retry_count == 1
        assert result.error is None

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Network timeouts are captured as errors after exhausting retries."""
        adapter = OpenAIAdapter(
            endpoint_url=OPENAI_URL,
            api_key="sk-test-key",
            timeout=1,
        )

        def timeout_side_effect(request):
            raise httpx.ConnectTimeout("Connection timed out")

        with respx.mock:
            respx.post(OPENAI_URL).mock(side_effect=timeout_side_effect)
            result = await adapter.generate(
                "Hello",
                {},
                runtime_options={"retries": 1},
            )

        assert result.output_text == ""
        assert result.error is not None
        assert "timed out" in result.error.lower()
        assert result.retry_count == 1

    @pytest.mark.asyncio
    async def test_inference_params_forwarded(self):
        """Inference params (temperature, max_tokens, etc.) appear in request body."""
        adapter = OpenAIAdapter(endpoint_url=OPENAI_URL, api_key="sk-test-key")
        captured_body = {}

        def capture_request(request):
            import json

            captured_body.update(json.loads(request.content))
            return httpx.Response(200, json=_openai_response())

        with respx.mock:
            respx.post(OPENAI_URL).mock(side_effect=capture_request)
            await adapter.generate(
                "Test",
                {"temperature": 0.3, "max_tokens": 100, "top_p": 0.9},
            )

        assert captured_body["temperature"] == 0.3
        assert captured_body["max_tokens"] == 100
        assert captured_body["top_p"] == 0.9


# ── Anthropic Adapter ──


class TestAnthropicAdapter:
    """Tests for AnthropicAdapter against mock HTTP server."""

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        """Adapter parses a normal Anthropic messages response correctly."""
        adapter = AnthropicAdapter(
            endpoint_url=ANTHROPIC_URL,
            api_key="sk-ant-test-key",
            model_name="claude-sonnet-4-20250514",
        )
        with respx.mock:
            respx.post(ANTHROPIC_URL).mock(
                return_value=httpx.Response(
                    200,
                    json=_anthropic_response("Claude says hello!", 20, 15),
                )
            )
            result = await adapter.generate("Say hello", {"max_tokens": 256})

        assert result.output_text == "Claude says hello!"
        assert result.prompt_tokens == 20
        assert result.completion_tokens == 15
        assert result.total_tokens == 35
        assert result.latency_ms > 0
        assert result.error is None
        assert result.raw_response is not None
        assert result.raw_response["id"] == "msg_test456"

    @pytest.mark.asyncio
    async def test_multi_block_response(self):
        """Multiple text content blocks are concatenated."""
        adapter = AnthropicAdapter(
            endpoint_url=ANTHROPIC_URL,
            api_key="sk-ant-test-key",
        )
        response_data = {
            "id": "msg_multi",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-20250514",
            "content": [
                {"type": "text", "text": "Part one. "},
                {"type": "text", "text": "Part two."},
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 10},
        }
        with respx.mock:
            respx.post(ANTHROPIC_URL).mock(return_value=httpx.Response(200, json=response_data))
            result = await adapter.generate("Multi-block test", {})

        assert result.output_text == "Part one. Part two."

    @pytest.mark.asyncio
    async def test_api_key_header(self):
        """Anthropic uses x-api-key header, not Bearer auth."""
        adapter = AnthropicAdapter(
            endpoint_url=ANTHROPIC_URL,
            api_key="sk-ant-test-key",
        )
        captured_headers = {}

        def capture_request(request):
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json=_anthropic_response())

        with respx.mock:
            respx.post(ANTHROPIC_URL).mock(side_effect=capture_request)
            await adapter.generate("Hi", {})

        assert captured_headers.get("x-api-key") == "sk-ant-test-key"
        assert captured_headers.get("anthropic-version") == "2023-06-01"

    @pytest.mark.asyncio
    async def test_system_prompt_in_body(self):
        """System prompt is sent as top-level 'system' field, not in messages."""
        adapter = AnthropicAdapter(
            endpoint_url=ANTHROPIC_URL,
            api_key="sk-ant-test-key",
        )
        captured_body = {}

        def capture_request(request):
            import json

            captured_body.update(json.loads(request.content))
            return httpx.Response(200, json=_anthropic_response())

        with respx.mock:
            respx.post(ANTHROPIC_URL).mock(side_effect=capture_request)
            await adapter.generate(
                "Hello",
                {},
                runtime_options={"system_prompt": "Be concise."},
            )

        assert captured_body["system"] == "Be concise."
        # Only one user message, no system message in messages list
        assert len(captured_body["messages"]) == 1
        assert captured_body["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_rate_limit_429(self):
        """429 rate limit errors are captured with status code in error string."""
        adapter = AnthropicAdapter(
            endpoint_url=ANTHROPIC_URL,
            api_key="sk-ant-test-key",
        )
        error_body = {
            "type": "error",
            "error": {"type": "rate_limit_error", "message": "Rate limit exceeded"},
        }
        with respx.mock:
            respx.post(ANTHROPIC_URL).mock(return_value=httpx.Response(429, json=error_body))
            result = await adapter.generate("Hello", {"max_tokens": 100})

        assert result.output_text == ""
        assert result.error is not None
        assert "429" in result.error
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_http_500_error(self):
        """Server errors are captured gracefully."""
        adapter = AnthropicAdapter(
            endpoint_url=ANTHROPIC_URL,
            api_key="sk-ant-test-key",
        )
        with respx.mock:
            respx.post(ANTHROPIC_URL).mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )
            result = await adapter.generate("Hello", {})

        assert result.output_text == ""
        assert result.error is not None
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Network timeouts are captured as errors."""
        adapter = AnthropicAdapter(
            endpoint_url=ANTHROPIC_URL,
            api_key="sk-ant-test-key",
            timeout=1,
        )

        def timeout_side_effect(request):
            raise httpx.ReadTimeout("Read timed out")

        with respx.mock:
            respx.post(ANTHROPIC_URL).mock(side_effect=timeout_side_effect)
            result = await adapter.generate("Hello", {})

        assert result.output_text == ""
        assert result.error is not None
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_inference_params_forwarded(self):
        """Inference params (temperature, stop_sequences) appear in request body."""
        adapter = AnthropicAdapter(endpoint_url=ANTHROPIC_URL, api_key="sk-ant-test-key")
        captured_body = {}

        def capture_request(request):
            import json

            captured_body.update(json.loads(request.content))
            return httpx.Response(200, json=_anthropic_response())

        with respx.mock:
            respx.post(ANTHROPIC_URL).mock(side_effect=capture_request)
            await adapter.generate(
                "Test",
                {"temperature": 0.2, "max_tokens": 512, "stop_sequences": ["\n"]},
            )

        assert captured_body["temperature"] == 0.2
        assert captured_body["max_tokens"] == 512
        assert captured_body["stop_sequences"] == ["\n"]


# ── Generic HTTP Adapter ──


class TestGenericHTTPAdapter:
    """Tests for GenericHTTPAdapter against mock HTTP server."""

    @pytest.mark.asyncio
    async def test_successful_generation_default_path(self):
        """Default response_text_path='output' extracts top-level 'output' key."""
        adapter = GenericHTTPAdapter(
            endpoint_url=GENERIC_URL,
            model_name="custom-model",
        )
        response_data = {"output": "Generated text here", "metadata": {"tokens": 42}}
        with respx.mock:
            respx.post(GENERIC_URL).mock(return_value=httpx.Response(200, json=response_data))
            result = await adapter.generate("Test prompt", {})

        assert result.output_text == "Generated text here"
        assert result.latency_ms > 0
        assert result.error is None
        assert result.raw_response == response_data

    @pytest.mark.asyncio
    async def test_successful_generation_nested_path(self):
        """Dot-separated response_text_path navigates nested dicts."""
        adapter = GenericHTTPAdapter(
            endpoint_url=GENERIC_URL,
            model_name="custom-model",
        )
        response_data = {"result": {"text": "Nested output"}, "status": "ok"}
        with respx.mock:
            respx.post(GENERIC_URL).mock(return_value=httpx.Response(200, json=response_data))
            result = await adapter.generate(
                "Test prompt",
                {},
                runtime_options={"response_text_path": "result.text"},
            )

        assert result.output_text == "Nested output"

    @pytest.mark.asyncio
    async def test_custom_prompt_field(self):
        """request_body_template.prompt_field controls which key holds the prompt."""
        adapter = GenericHTTPAdapter(endpoint_url=GENERIC_URL)
        captured_body = {}

        def capture_request(request):
            import json

            captured_body.update(json.loads(request.content))
            return httpx.Response(200, json={"output": "ok"})

        with respx.mock:
            respx.post(GENERIC_URL).mock(side_effect=capture_request)
            await adapter.generate(
                "Hello custom",
                {"temperature": 0.5},
                runtime_options={
                    "request_body_template": {
                        "prompt_field": "input_text",
                        "base_body": {"model": "my-model"},
                    },
                },
            )

        assert captured_body["input_text"] == "Hello custom"
        assert captured_body["model"] == "my-model"
        assert captured_body["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_custom_headers(self):
        """Extra headers from runtime_options are included in the request."""
        adapter = GenericHTTPAdapter(endpoint_url=GENERIC_URL)
        captured_headers = {}

        def capture_request(request):
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"output": "ok"})

        with respx.mock:
            respx.post(GENERIC_URL).mock(side_effect=capture_request)
            await adapter.generate(
                "Hello",
                {},
                runtime_options={"headers": {"X-Custom-Auth": "token-abc"}},
            )

        assert captured_headers.get("x-custom-auth") == "token-abc"

    @pytest.mark.asyncio
    async def test_http_error(self):
        """HTTP errors from custom endpoints are captured gracefully."""
        adapter = GenericHTTPAdapter(endpoint_url=GENERIC_URL)
        with respx.mock:
            respx.post(GENERIC_URL).mock(
                return_value=httpx.Response(503, text="Service Unavailable")
            )
            result = await adapter.generate("Hello", {})

        assert result.output_text == ""
        assert result.error is not None
        assert "503" in result.error

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Network timeouts on custom endpoints are captured as errors."""
        adapter = GenericHTTPAdapter(endpoint_url=GENERIC_URL, timeout=1)

        def timeout_side_effect(request):
            raise httpx.ConnectTimeout("Connection timed out")

        with respx.mock:
            respx.post(GENERIC_URL).mock(side_effect=timeout_side_effect)
            result = await adapter.generate("Hello", {})

        assert result.output_text == ""
        assert result.error is not None
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_missing_response_path_returns_empty(self):
        """When response_text_path points to a missing key, output is empty string."""
        adapter = GenericHTTPAdapter(endpoint_url=GENERIC_URL)
        response_data = {"data": {"result": "value"}}
        with respx.mock:
            respx.post(GENERIC_URL).mock(return_value=httpx.Response(200, json=response_data))
            result = await adapter.generate(
                "Test",
                {},
                runtime_options={"response_text_path": "data.nonexistent.path"},
            )

        assert result.output_text == ""
