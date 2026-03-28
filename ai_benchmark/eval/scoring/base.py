"""Base scorer interface and scorer registry."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class ScorerResult:
    """Result from a single scorer evaluation."""

    scorer_type: str
    score: float  # 0.0–1.0 (or scale_min–scale_max for rubric/judge)
    passed: bool
    details: dict = field(default_factory=dict)


class BaseScorer(abc.ABC):
    """Abstract interface for all scorers."""

    scorer_type: str = "base"

    def __init__(self, config: dict):
        self.config = config

    @abc.abstractmethod
    async def score(
        self,
        *,
        output: str,
        expected: str | None = None,
        input_text: str | None = None,
        context: str | None = None,
        metadata: dict | None = None,
    ) -> ScorerResult:
        """Score a single output against optional expected/context."""
        ...


# Scorer type → class registry
_SCORER_REGISTRY: dict[str, type[BaseScorer]] = {}


def register_scorer(scorer_type: str, cls: type[BaseScorer]) -> None:
    _SCORER_REGISTRY[scorer_type] = cls


def resolve_scorer(scorer_type: str, config: dict) -> BaseScorer:
    cls = _SCORER_REGISTRY.get(scorer_type)
    if cls is None:
        raise ValueError(
            f"No scorer registered for type '{scorer_type}'. "
            f"Available: {list(_SCORER_REGISTRY.keys())}"
        )
    return cls(config)
