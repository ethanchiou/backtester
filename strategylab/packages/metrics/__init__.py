"""
strategylab.metrics — Performance calculation functions.

Public API
----------
compute_metrics   compute all metrics from equity + trade log
MetricsResult     result container dataclass
"""

from .calculator import MetricsResult, compute_metrics

__all__ = ["compute_metrics", "MetricsResult"]
