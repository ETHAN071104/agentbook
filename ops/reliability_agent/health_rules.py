from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ops.reliability_agent.models import (
    BackupHealthInput,
    ClusterHealthInput,
    HealthCheck,
    HealthStatus,
    RestoreHealthInput,
    VersionHealthInput,
)


BACKUP_MINIMUM_TOLERANCE_MINUTES = 60
RESTORE_PENDING_WARNING_HOURS = 6
VERSION_SUPPORT_WARNING_DAYS = 90

_HEALTHY_CLUSTER_STATES = {
    "AVAILABLE",
    "CLUSTER_STATE_AVAILABLE",
    "CLUSTER_STATE_CREATED",
    "CREATED",
    "READY",
    "RUNNING",
}
_WARNING_CLUSTER_STATES = {
    "CLUSTER_STATE_CREATING",
    "CLUSTER_STATE_UPDATING",
    "CREATING",
    "MAINTENANCE",
    "UPDATING",
    "UPGRADING",
}
_CRITICAL_CLUSTER_STATES = {
    "CLUSTER_STATE_FAILED",
    "CLUSTER_STATE_UNAVAILABLE",
    "DELETED",
    "FAILED",
    "STOPPED",
    "SUSPENDED",
    "UNAVAILABLE",
}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC)


def evaluate_cluster(value: ClusterHealthInput | None) -> HealthCheck:
    if value is None or not value.state:
        return HealthCheck(
            key="cluster_availability",
            title="Cluster availability",
            status=HealthStatus.UNKNOWN,
            summary="Cluster availability could not be determined.",
            recommended_action=(
                "Verify ccloud permissions and confirm the installed output format."
            ),
        )
    state = value.state.strip().upper()
    details = {
        "state": state,
        "plan_type": value.plan_type,
        "cloud_provider": value.cloud_provider,
        "regions": list(value.regions),
        "cockroachdb_version": value.cockroachdb_version,
        "resource_limit_or_hardware": value.resource_limit_or_hardware,
    }
    if state in _HEALTHY_CLUSTER_STATES:
        return HealthCheck(
            key="cluster_availability",
            title="Cluster availability",
            status=HealthStatus.HEALTHY,
            summary="The target CockroachDB Cloud cluster reports an available state.",
            details=details,
        )
    if state in _WARNING_CLUSTER_STATES:
        return HealthCheck(
            key="cluster_availability",
            title="Cluster availability",
            status=HealthStatus.WARNING,
            summary=f"The cluster is in a transitional state: {state}.",
            details=details,
            recommended_action=(
                "Monitor the cluster in CockroachDB Cloud until it returns to an "
                "available state."
            ),
        )
    if state in _CRITICAL_CLUSTER_STATES:
        return HealthCheck(
            key="cluster_availability",
            title="Cluster availability",
            status=HealthStatus.CRITICAL,
            summary=f"The cluster reports an unavailable or failed state: {state}.",
            details=details,
            recommended_action=(
                "Investigate the cluster state in CockroachDB Cloud and follow "
                "the approved incident process."
            ),
        )
    return HealthCheck(
        key="cluster_availability",
        title="Cluster availability",
        status=HealthStatus.UNKNOWN,
        summary=f"The cluster returned an unrecognized state: {state}.",
        details=details,
        recommended_action="Confirm the state against the current ccloud documentation.",
    )


def evaluate_backup_configuration(
    value: BackupHealthInput | None,
) -> HealthCheck:
    if value is None or value.enabled is None:
        return HealthCheck(
            key="managed_backup_configuration",
            title="Managed backup configuration",
            status=HealthStatus.UNKNOWN,
            summary="Managed backup configuration could not be determined.",
            recommended_action=(
                "Verify backup-read permissions and plan support in CockroachDB Cloud."
            ),
        )
    details = {
        "enabled": value.enabled,
        "frequency_minutes": value.frequency_minutes,
        "retention_days": value.retention_days,
    }
    if value.enabled is False:
        return HealthCheck(
            key="managed_backup_configuration",
            title="Managed backup configuration",
            status=HealthStatus.CRITICAL,
            summary="Managed backups are explicitly disabled.",
            details=details,
            recommended_action=(
                "Review the approved backup policy in CockroachDB Cloud. "
                "This read-only agent will not change it."
            ),
        )
    if value.frequency_minutes is None or value.retention_days is None:
        return HealthCheck(
            key="managed_backup_configuration",
            title="Managed backup configuration",
            status=HealthStatus.UNKNOWN,
            summary=(
                "Managed backups are enabled, but frequency or retention was not exposed."
            ),
            details=details,
            recommended_action=(
                "Confirm frequency and retention in CockroachDB Cloud for this plan."
            ),
        )
    return HealthCheck(
        key="managed_backup_configuration",
        title="Managed backup configuration",
        status=HealthStatus.HEALTHY,
        summary=(
            "Managed backups are enabled with visible frequency and retention settings."
        ),
        details=details,
    )


def evaluate_backup_freshness(
    value: BackupHealthInput | None,
    *,
    now: datetime,
) -> HealthCheck:
    if value is None or value.enabled is None:
        return HealthCheck(
            key="backup_freshness",
            title="Backup freshness",
            status=HealthStatus.UNKNOWN,
            summary="Backup freshness could not be determined.",
            recommended_action="Verify backup-list access for the configured cluster.",
        )
    details = {
        "latest_backup_time": (
            value.latest_backup_time.isoformat()
            if value.latest_backup_time is not None
            else None
        ),
        "latest_backup_status": value.latest_backup_status,
        "backup_count_observed": value.backup_count_observed,
        "frequency_minutes": value.frequency_minutes,
    }
    if value.enabled is False:
        return HealthCheck(
            key="backup_freshness",
            title="Backup freshness",
            status=HealthStatus.CRITICAL,
            summary="No freshness guarantee can be evaluated while backups are disabled.",
            details=details,
            recommended_action="Review the approved managed-backup policy.",
        )
    status = (value.latest_backup_status or "").strip().upper()
    if status in {"FAILED", "ERROR"}:
        return HealthCheck(
            key="backup_freshness",
            title="Backup freshness",
            status=HealthStatus.CRITICAL,
            summary="The latest visible backup reports a failed status.",
            details=details,
            recommended_action=(
                "Investigate the failed backup in CockroachDB Cloud without "
                "starting a restore from this tool."
            ),
        )
    if value.latest_backup_time is None:
        return HealthCheck(
            key="backup_freshness",
            title="Backup freshness",
            status=HealthStatus.WARNING,
            summary="Backups are enabled, but no backup was visible.",
            details=details,
            recommended_action=(
                "Confirm cluster age and backup visibility in CockroachDB Cloud."
            ),
        )
    if value.frequency_minutes is None:
        return HealthCheck(
            key="backup_freshness",
            title="Backup freshness",
            status=HealthStatus.UNKNOWN,
            summary=(
                "A backup was visible, but freshness cannot be scored without frequency."
            ),
            details=details,
            recommended_action="Confirm the managed-backup frequency for this plan.",
        )
    age_minutes = max(
        0,
        int((_utc(now) - _utc(value.latest_backup_time)).total_seconds() // 60),
    )
    tolerance = max(
        value.frequency_minutes * 2,
        value.frequency_minutes + BACKUP_MINIMUM_TOLERANCE_MINUTES,
    )
    details["age_minutes"] = age_minutes
    details["freshness_tolerance_minutes"] = tolerance
    if age_minutes <= tolerance:
        return HealthCheck(
            key="backup_freshness",
            title="Backup freshness",
            status=HealthStatus.HEALTHY,
            summary="The latest visible backup is within the configured freshness tolerance.",
            details=details,
        )
    return HealthCheck(
        key="backup_freshness",
        title="Backup freshness",
        status=HealthStatus.WARNING,
        summary="The latest visible backup is older than the freshness tolerance.",
        details=details,
        recommended_action=(
            "Review backup activity in CockroachDB Cloud; this report does not "
            "prove recoverability."
        ),
    )


def evaluate_restores(
    value: RestoreHealthInput | None,
    *,
    now: datetime,
) -> HealthCheck:
    if value is None:
        return HealthCheck(
            key="restore_status",
            title="Restore status",
            status=HealthStatus.UNKNOWN,
            summary="Restore history could not be determined.",
            recommended_action="Verify restore-list access for the configured cluster.",
        )
    details = {
        "total_restore_count": value.total_restore_count,
        "failed_count": value.failed_count,
        "pending_count": value.pending_count,
        "incomplete_count": value.incomplete_count,
        "latest_restore_time": (
            value.latest_restore_time.isoformat()
            if value.latest_restore_time is not None
            else None
        ),
        "latest_restore_status": value.latest_restore_status,
    }
    if value.failed_count > 0:
        return HealthCheck(
            key="restore_status",
            title="Restore status",
            status=HealthStatus.WARNING,
            summary="One or more failed restore records were observed.",
            details=details,
            recommended_action=(
                "Review the failed restore records in CockroachDB Cloud. "
                "This agent will not retry or create a restore."
            ),
        )
    open_count = value.pending_count + value.incomplete_count
    if open_count > 0:
        if value.oldest_open_restore_time is None:
            return HealthCheck(
                key="restore_status",
                title="Restore status",
                status=HealthStatus.UNKNOWN,
                summary=(
                    "Open restore records were observed, but their age was unavailable."
                ),
                details=details,
                recommended_action="Inspect the open restores in CockroachDB Cloud.",
            )
        age = _utc(now) - _utc(value.oldest_open_restore_time)
        details["oldest_open_restore_age_hours"] = round(
            age.total_seconds() / 3600,
            2,
        )
        if age > timedelta(hours=RESTORE_PENDING_WARNING_HOURS):
            return HealthCheck(
                key="restore_status",
                title="Restore status",
                status=HealthStatus.WARNING,
                summary=(
                    "A pending or incomplete restore has exceeded the "
                    f"{RESTORE_PENDING_WARNING_HOURS}-hour observation threshold."
                ),
                details=details,
                recommended_action="Inspect the long-running restore in CockroachDB Cloud.",
            )
        return HealthCheck(
            key="restore_status",
            title="Restore status",
            status=HealthStatus.HEALTHY,
            summary=(
                "An open restore was observed within the documented monitoring threshold."
            ),
            details=details,
        )
    if value.total_restore_count == 0:
        summary = "No restore records were observed."
    else:
        summary = "Managed backups were observed and no failed restore record was found."
    return HealthCheck(
        key="restore_status",
        title="Restore status",
        status=HealthStatus.HEALTHY,
        summary=summary,
        details=details,
    )


def evaluate_version(
    value: VersionHealthInput | None,
    *,
    now: datetime,
) -> HealthCheck:
    if (
        value is None
        or value.running_major_version is None
        or value.support_status is None
    ):
        return HealthCheck(
            key="version_support",
            title="Version support",
            status=HealthStatus.UNKNOWN,
            summary="The running CockroachDB major version could not be matched.",
            recommended_action=(
                "Compare the running version with `ccloud cluster versions`."
            ),
        )
    status = value.support_status.strip().upper()
    details = {
        "running_major_version": value.running_major_version,
        "support_status": status,
        "support_end": (
            value.support_end.date().isoformat()
            if value.support_end is not None
            else None
        ),
        "allowed_upgrade_targets": list(value.allowed_upgrade_targets),
    }
    if status in {"UNSUPPORTED", "EOL", "END_OF_LIFE"}:
        return HealthCheck(
            key="version_support",
            title="Version support",
            status=HealthStatus.CRITICAL,
            summary="The running CockroachDB major version is marked unsupported.",
            details=details,
            recommended_action=(
                "Plan an approved upgrade using CockroachDB Cloud. "
                "This agent will not change version policy."
            ),
        )
    if status != "SUPPORTED":
        return HealthCheck(
            key="version_support",
            title="Version support",
            status=HealthStatus.UNKNOWN,
            summary=f"The version support status was not recognized: {status}.",
            details=details,
            recommended_action="Confirm the status in CockroachDB Cloud.",
        )
    if value.support_end is not None:
        remaining = _utc(value.support_end) - _utc(now)
        details["support_days_remaining"] = int(remaining.total_seconds() // 86400)
        if remaining <= timedelta(days=VERSION_SUPPORT_WARNING_DAYS):
            return HealthCheck(
                key="version_support",
                title="Version support",
                status=HealthStatus.WARNING,
                summary=(
                    "The running CockroachDB major version is supported, but "
                    f"support ends within {VERSION_SUPPORT_WARNING_DAYS} days."
                ),
                details=details,
                recommended_action=(
                    "Review the allowed upgrade targets and schedule an approved upgrade."
                ),
            )
    return HealthCheck(
        key="version_support",
        title="Version support",
        status=HealthStatus.HEALTHY,
        summary="The running CockroachDB major version is marked supported.",
        details=details,
    )


def overall_status(checks: tuple[HealthCheck, ...]) -> HealthStatus:
    precedence = {
        HealthStatus.HEALTHY: 0,
        HealthStatus.UNKNOWN: 1,
        HealthStatus.WARNING: 2,
        HealthStatus.CRITICAL: 3,
    }
    if not checks:
        return HealthStatus.UNKNOWN
    return max((check.status for check in checks), key=precedence.__getitem__)
