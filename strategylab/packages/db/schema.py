"""
db/schema.py — SQLAlchemy ORM models for StrategyLab.

Tables
------
strategies  — saved strategy definitions + favorite flag
runs        — backtest run records with metrics and equity data
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class Strategy(Base):
    """A saved trading strategy."""

    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    version = Column(String(20), nullable=False, default="1.0")
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)          # JSON array string
    module_path = Column(String(255), nullable=True)  # importable path
    favorite = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=func.now())

    runs = relationship("Run", back_populates="strategy", cascade="all, delete-orphan")

    def tags_list(self) -> list[str]:
        """Deserialise tags from JSON string to list."""
        if self.tags is None:
            return []
        try:
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tags(self, tags: list[str]) -> None:
        """Serialise a list of tag strings to JSON."""
        self.tags = json.dumps(tags)

    def __repr__(self) -> str:
        return f"<Strategy id={self.id} name={self.name!r}>"


class Run(Base):
    """A completed backtest run."""

    __tablename__ = "runs"

    run_id = Column(String(36), primary_key=True)        # UUID
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    parameters = Column(Text, nullable=True)              # JSON object
    date_range_start = Column(String(10), nullable=True)  # YYYY-MM-DD
    date_range_end = Column(String(10), nullable=True)
    symbols = Column(Text, nullable=True)                  # JSON array
    mode = Column(String(20), nullable=False, default="single")  # "single"|"portfolio"
    execution_settings = Column(Text, nullable=True)       # JSON object
    metrics_json = Column(Text, nullable=True)             # JSON object
    equity_json = Column(Text, nullable=True)              # JSON {date: value}
    created_at = Column(DateTime, nullable=False, default=func.now())

    strategy = relationship("Strategy", back_populates="runs")

    def get_parameters(self) -> dict:
        return json.loads(self.parameters) if self.parameters else {}

    def get_symbols(self) -> list[str]:
        return json.loads(self.symbols) if self.symbols else []

    def get_metrics(self) -> dict:
        return json.loads(self.metrics_json) if self.metrics_json else {}

    def get_equity(self) -> dict:
        return json.loads(self.equity_json) if self.equity_json else {}

    def __repr__(self) -> str:
        return f"<Run run_id={self.run_id!r} strategy_id={self.strategy_id}>"
