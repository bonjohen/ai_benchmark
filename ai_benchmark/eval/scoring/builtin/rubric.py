"""Rubric-based scorer — evaluates output against textual criteria."""

from __future__ import annotations

from ..base import BaseScorer, ScorerResult, register_scorer


class RubricScorer(BaseScorer):
    """Score output against rubric criteria on a configurable scale.

    Config:
        rubric_text: str — criteria description
        scale_min: float — minimum score (default 0)
        scale_max: float — maximum score (default 5)
        pass_threshold: float — minimum score to pass (default 3)
        dimensions: list[dict] — optional multi-dimension rubric with
            {name, description, weight} per dimension
    """

    scorer_type = "rubric"

    async def score(
        self,
        *,
        output: str,
        expected: str | None = None,
        input_text: str | None = None,
        context: str | None = None,
        metadata: dict | None = None,
    ) -> ScorerResult:
        scale_min = self.config.get("scale_min", 0)
        scale_max = self.config.get("scale_max", 5)
        pass_threshold = self.config.get("pass_threshold", 3)
        dimensions = self.config.get("dimensions", [])

        # Simple heuristic scoring without a judge model:
        # Check for keyword/phrase presence from rubric
        rubric_text = self.config.get("rubric_text", "")
        keywords = [k.strip().lower() for k in rubric_text.split(",") if k.strip()]

        if not keywords:
            # No rubric criteria → score based on whether output is non-empty
            raw_score = scale_max if output.strip() else scale_min
        else:
            output_lower = output.lower()
            hits = sum(1 for k in keywords if k in output_lower)
            ratio = hits / len(keywords)
            raw_score = scale_min + ratio * (scale_max - scale_min)

        # Multi-dimension scoring
        dimension_scores = {}
        if dimensions:
            for dim in dimensions:
                dim_name = dim.get("name", "unknown")
                dim_keywords = [
                    k.strip().lower() for k in dim.get("description", "").split(",") if k.strip()
                ]
                if dim_keywords:
                    output_lower = output.lower()
                    dim_hits = sum(1 for k in dim_keywords if k in output_lower)
                    dim_ratio = dim_hits / len(dim_keywords)
                    dim_score = scale_min + dim_ratio * (scale_max - scale_min)
                else:
                    dim_score = raw_score
                dimension_scores[dim_name] = dim_score

            # Weighted average
            total_weight = sum(d.get("weight", 1.0) for d in dimensions)
            if total_weight > 0:
                raw_score = (
                    sum(
                        dimension_scores.get(d.get("name", ""), 0) * d.get("weight", 1.0)
                        for d in dimensions
                    )
                    / total_weight
                )

        # Normalize to 0-1 for the ScorerResult score field
        normalized = (
            (raw_score - scale_min) / (scale_max - scale_min) if scale_max > scale_min else 0.0
        )

        return ScorerResult(
            scorer_type=self.scorer_type,
            score=normalized,
            passed=raw_score >= pass_threshold,
            details={
                "raw_score": raw_score,
                "scale_min": scale_min,
                "scale_max": scale_max,
                "pass_threshold": pass_threshold,
                "dimension_scores": dimension_scores or None,
            },
        )


register_scorer("rubric", RubricScorer)
