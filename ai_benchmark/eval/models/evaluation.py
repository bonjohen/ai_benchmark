"""EvaluationDefinition and EvaluationVersion data models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...models.base import Base


class EvaluationDefinition(Base):
    __tablename__ = "evaluation_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of strings
    suite_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    execution_mode: Mapped[str] = mapped_column(
        String(50), nullable=False, default="sequential"
    )  # sequential | parallel | matrix
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    versions: Mapped[list[EvaluationVersion]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )


class EvaluationVersion(Base):
    __tablename__ = "evaluation_versions"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_id", "version_number", name="uq_evaluation_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_definitions.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_version_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=False
    )
    scorer_config: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON: list of {scorer_version_id, weight, pass_threshold}
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    preprocessing: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    pass_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    evaluation: Mapped[EvaluationDefinition] = relationship(back_populates="versions")
    dataset_version: Mapped[DatasetVersion] = relationship()  # noqa: F821

    runs: Mapped[list[Run]] = relationship(back_populates="evaluation_version")  # noqa: F821
