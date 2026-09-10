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


def _env_list(name: str) -> tuple:
    """Parse a comma-separated environment variable into a tuple."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class ScalingConfig:
    """Horizontal scaling, traffic control and observability settings.

    Every value can be overridden with an environment variable so the same code
    runs as a single-node hackathon demo or as N replicas behind
    Nginx / Apache httpd / Microsoft IIS. Nothing here changes the model.
    """

    # Identity + topology
    instance_id: str = os.getenv("JAN_DRISHTI_INSTANCE_ID", f"node-{os.getpid()}")
    pid: int = os.getpid()
    environment: str = os.getenv("JAN_DRISHTI_ENV", "demo")
    # Base URLs of the other app replicas, e.g.
    # JAN_DRISHTI_CLUSTER_NODES=http://127.0.0.1:8001,http://127.0.0.1:8002
    cluster_nodes: tuple = _env_list("JAN_DRISHTI_CLUSTER_NODES")
    public_url: str = os.getenv("JAN_DRISHTI_PUBLIC_URL", "")
    # Shared secret used by replicas to read each other's /api/cluster/self
    cluster_token: str = os.getenv("JAN_DRISHTI_CLUSTER_TOKEN", "jandrishti-cluster-demo")
    peer_timeout_seconds: float = float(os.getenv("JAN_DRISHTI_PEER_TIMEOUT", "0.8"))
    peer_cache_seconds: float = float(os.getenv("JAN_DRISHTI_PEER_CACHE", "1.0"))
    # Which edge tier sits in front of the app (nginx | apache | iis | traefik | none)
    proxy_layer: str = os.getenv("JAN_DRISHTI_PROXY_LAYER", "none").strip().lower()

    # Traffic control defaults (runtime-tunable from the dashboard)
    rate_limit_enabled: bool = os.getenv("JAN_DRISHTI_RATE_LIMIT_ENABLED", "1") not in {"0", "false", "no"}
    rate_limit_rps: float = float(os.getenv("JAN_DRISHTI_RATE_LIMIT_RPS", "25"))
    rate_limit_burst: int = int(os.getenv("JAN_DRISHTI_RATE_LIMIT_BURST", "60"))
    max_concurrent: int = int(os.getenv("JAN_DRISHTI_MAX_CONCURRENT", "64"))
    load_shed_enabled: bool = os.getenv("JAN_DRISHTI_LOAD_SHED", "1") not in {"0", "false", "no"}
    lb_algorithm: str = os.getenv("JAN_DRISHTI_LB_ALGORITHM", "least_conn")

    # Autoscaling signals (recommendation only, no orchestrator required)
    autoscale_enabled: bool = os.getenv("JAN_DRISHTI_AUTOSCALE", "1") not in {"0", "false", "no"}
    autoscale_target_p95_ms: float = float(os.getenv("JAN_DRISHTI_TARGET_P95_MS", "250"))
    autoscale_rps_per_node: float = float(os.getenv("JAN_DRISHTI_RPS_PER_NODE", "40"))
    autoscale_min_nodes: int = int(os.getenv("JAN_DRISHTI_MIN_NODES", "2"))
    autoscale_max_nodes: int = int(os.getenv("JAN_DRISHTI_MAX_NODES", "12"))

    # Caches + telemetry windows
    asset_cache_max_entries: int = int(os.getenv("JAN_DRISHTI_ASSET_CACHE_ENTRIES", "64"))
    asset_cache_ttl_seconds: float = float(os.getenv("JAN_DRISHTI_ASSET_CACHE_TTL", "300"))
    analysis_cache_entries: int = int(os.getenv("JAN_DRISHTI_ANALYSIS_CACHE_ENTRIES", "8"))
    latency_reservoir: int = int(os.getenv("JAN_DRISHTI_LATENCY_RESERVOIR", "1024"))
    series_window_seconds: int = int(os.getenv("JAN_DRISHTI_SERIES_WINDOW", "180"))
    recent_request_log: int = int(os.getenv("JAN_DRISHTI_RECENT_LOG", "40"))
    event_log: int = int(os.getenv("JAN_DRISHTI_EVENT_LOG", "60"))


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
SCALING = ScalingConfig()
