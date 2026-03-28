"""Format validation scorer — checks JSON, XML, markdown, code format."""

from __future__ import annotations

import json
import re

from ..base import BaseScorer, ScorerResult, register_scorer


class FormatValidatorScorer(BaseScorer):
    """Score 1.0 if output matches the expected format, 0.0 otherwise.

    Config:
        expected_format: str — "json", "xml", "markdown", "code"
        schema: dict | None — optional JSON Schema for json format
    """

    scorer_type = "format_validator"

    async def score(
        self,
        *,
        output: str,
        expected: str | None = None,
        input_text: str | None = None,
        context: str | None = None,
        metadata: dict | None = None,
    ) -> ScorerResult:
        fmt = self.config.get("expected_format", "json")
        errors: list[str] = []

        if fmt == "json":
            valid = self._validate_json(output, errors)
        elif fmt == "xml":
            valid = self._validate_xml(output, errors)
        elif fmt == "markdown":
            valid = self._validate_markdown(output, errors)
        elif fmt == "code":
            valid = self._validate_code(output, errors)
        else:
            valid = False
            errors.append(f"Unknown format: {fmt}")

        return ScorerResult(
            scorer_type=self.scorer_type,
            score=1.0 if valid else 0.0,
            passed=valid,
            details={"expected_format": fmt, "errors": errors},
        )

    def _validate_json(self, text: str, errors: list[str]) -> bool:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
            return False

        schema = self.config.get("schema")
        if schema:
            try:
                import jsonschema

                jsonschema.validate(parsed, schema)
            except ImportError:
                pass  # jsonschema not installed; skip validation
            except Exception as e:
                errors.append(f"Schema validation failed: {e}")
                return False
        return True

    def _validate_xml(self, text: str, errors: list[str]) -> bool:
        try:
            import xml.etree.ElementTree as ET

            ET.fromstring(text)
            return True
        except ET.ParseError as e:
            errors.append(f"Invalid XML: {e}")
            return False

    def _validate_markdown(self, text: str, errors: list[str]) -> bool:
        # Check for at least one markdown structural element
        md_patterns = [
            r"^#{1,6}\s",  # headers
            r"^\*\s|^-\s|^\d+\.\s",  # lists
            r"```",  # code blocks
            r"\[.*\]\(.*\)",  # links
            r"\*\*.*\*\*|__.*__",  # bold
        ]
        for pattern in md_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True
        errors.append("No markdown structural elements found")
        return False

    def _validate_code(self, text: str, errors: list[str]) -> bool:
        # Heuristic: check for code-like patterns
        code_patterns = [
            r"(def |class |function |const |let |var |import |from |#include)",
            r"[{}\[\]();]",
            r"(if |else |for |while |return )",
        ]
        matches = sum(1 for p in code_patterns if re.search(p, text))
        if matches >= 2:
            return True
        errors.append("Text does not appear to be code")
        return False


register_scorer("format_validator", FormatValidatorScorer)
