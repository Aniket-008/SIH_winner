"""Central configuration for JAN-DRISHTI AI.

Keep tunable thresholds here so hackathon mentors or future maintainers can
change model behaviour without touching the UI or API layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import os


@dataclass(frozen=True)
class RiskThresholds:
    """Business thresholds used by the explainable AI engine."""

    medium_risk: int = 35
    high_risk: int = 60
    critical_risk: int = 80

    low_cost_overrun_pct: float = 5.0
    medium_cost_overrun_pct: float = 10.0
    high_cost_overrun_pct: float = 25.0
    critical_cost_overrun_pct: float = 50.0

    medium_financial_physical_gap_pct: float = 20.0
    high_financial_physical_gap_pct: float = 35.0

    stale_update_days: int = 45
    very_stale_update_days: int = 90

    medium_delay_days: int = 60
    high_delay_days: int = 180
    critical_delay_days: int = 365

    duplicate_name_similarity: float = 0.88
    duplicate_amount_tolerance_pct: float = 7.5

    schedule_slippage_medium_pct: float = 15.0
    schedule_slippage_high_pct: float = 30.0


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration shared by server and analysis modules."""

    app_name: str = "JAN-DRISHTI AI"
    host: str = os.getenv("JAN_DRISHTI_HOST", "0.0.0.0")
    port: int = int(os.getenv("JAN_DRISHTI_PORT", "8000"))
    max_upload_mb: int = int(os.getenv("JAN_DRISHTI_MAX_UPLOAD_MB", "50"))
    thresholds: RiskThresholds = field(default_factory=RiskThresholds)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def analysis_today() -> date:
    """Return the date used by the engine.

    The environment override makes demos/tests reproducible while production can
    default to the real current date.
    """

    override = os.getenv("JAN_DRISHTI_TODAY")
    if override:
        return date.fromisoformat(override)
    return date.today()


CONFIG = AppConfig()
