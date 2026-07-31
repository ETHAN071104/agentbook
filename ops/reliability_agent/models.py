from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Operation(str, Enum):
    GET_CLI_VERSION = "get_cli_version"
    GET_AUTHENTICATED_IDENTITY_STATUS = "get_authenticated_identity_status"
    LIST_CLUSTERS = "list_clusters"
    GET_CLUSTER_INFO = "get_cluster_info"
    GET_BACKUP_CONFIG = "get_backup_config"
    LIST_BACKUPS = "list_backups"
    LIST_RESTORES = "list_restores"
    LIST_SUPPORTED_VERSIONS = "list_supported_versions"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CommandResult:
    operation: Operation
    stdout: str
    return_code: int = 0


@dataclass(frozen=True)
class ClusterHealthInput:
    state: str | None
    plan_type: str | None
    cloud_provider: str | None
    regions: tuple[str, ...]
    cockroachdb_version: str | None
    resource_limit_or_hardware: str | None
    collected_at: datetime


@dataclass(frozen=True)
class BackupHealthInput:
    enabled: bool | None
    frequency_minutes: int | None
    retention_days: int | None
    latest_backup_time: datetime | None
    latest_backup_status: str | None
    backup_count_observed: int
    collected_at: datetime


@dataclass(frozen=True)
class RestoreHealthInput:
    total_restore_count: int
    failed_count: int
    pending_count: int
    incomplete_count: int
    latest_restore_time: datetime | None
    latest_restore_status: str | None
    collected_at: datetime
    oldest_open_restore_time: datetime | None = None


@dataclass(frozen=True)
class VersionHealthInput:
    running_major_version: str | None
    support_status: str | None
    support_end: datetime | None
    allowed_upgrade_targets: tuple[str, ...]
    collected_at: datetime


@dataclass(frozen=True)
class HealthCheck:
    key: str
    title: str
    status: HealthStatus
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    recommended_action: str | None = None


@dataclass(frozen=True)
class CollectionResult:
    cli_version: str | None
    cluster: ClusterHealthInput | None
    backup: BackupHealthInput | None
    restore: RestoreHealthInput | None
    version: VersionHealthInput | None
    commands_used: tuple[Operation, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReliabilityReport:
    report_version: str
    generated_at: datetime
    cluster_display_name: str
    overall_status: HealthStatus
    checks: tuple[HealthCheck, ...]
    warnings: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    data_access_statement: str
    commands_used: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.isoformat()
        payload["overall_status"] = self.overall_status.value
        payload["checks"] = [
            {
                **asdict(check),
                "status": check.status.value,
            }
            for check in self.checks
        ]
        return payload
