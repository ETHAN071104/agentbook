from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ops.reliability_agent.command_runner import (
    CCloudCommandRunner,
    CCloudExecutionFailure,
    CCloudNonzeroExit,
    ReliabilityCommandError,
    validate_cluster_name,
)
from ops.reliability_agent.models import CollectionResult, Operation
from ops.reliability_agent.parsers import (
    OutputParseError,
    parse_backup_health,
    parse_cli_version,
    parse_cluster_info,
    parse_cluster_names,
    parse_restore_health,
    parse_version_health,
)


class AuthenticationRequired(RuntimeError):
    pass


class TargetClusterNotConfigured(RuntimeError):
    def __init__(self, available_names: tuple[str, ...]) -> None:
        super().__init__(
            "More than one CockroachDB Cloud cluster is accessible. "
            "No cluster was selected automatically."
        )
        self.available_names = available_names


class NoAccessibleClusters(RuntimeError):
    pass


class TargetClusterNotFound(RuntimeError):
    pass


class TargetClusterSelectionFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class PrerequisiteResult:
    cli_version: str | None
    target_cluster: str
    auto_selected: bool = False


class ReliabilityCollector:
    def __init__(self, runner: CCloudCommandRunner | None = None) -> None:
        self.runner = runner or CCloudCommandRunner()

    def verify_prerequisites(
        self,
        configured_target: str | None,
    ) -> PrerequisiteResult:
        version_result = self.runner.run(Operation.GET_CLI_VERSION)
        try:
            cli_version = parse_cli_version(version_result.stdout)
        except OutputParseError:
            cli_version = None

        try:
            self.runner.run(Operation.GET_AUTHENTICATED_IDENTITY_STATUS)
        except CCloudNonzeroExit as error:
            raise AuthenticationRequired(
                "No valid ccloud human-administrator session was verified. "
                "Run `ccloud auth login` manually, then retry."
            ) from error

        try:
            clusters_result = self.runner.run(Operation.LIST_CLUSTERS)
        except CCloudExecutionFailure:
            raise
        except ReliabilityCommandError as error:
            raise TargetClusterSelectionFailed(
                "CockroachDB Cloud cluster selection could not read the "
                "accessible cluster list."
            ) from error
        try:
            available_names = parse_cluster_names(clusters_result.stdout)
        except OutputParseError as error:
            raise TargetClusterSelectionFailed(
                "Available clusters could not be read safely from ccloud output."
            ) from error
        auto_selected = False
        if configured_target is None:
            if not available_names:
                raise NoAccessibleClusters(
                    "No accessible CockroachDB Cloud cluster was found."
                )
            if len(available_names) > 1:
                raise TargetClusterNotConfigured(available_names)
            target = available_names[0]
            auto_selected = True
        else:
            target = validate_cluster_name(configured_target)
        if target not in available_names:
            raise TargetClusterNotFound(
                "The configured ccloud target cluster was not found. "
                "No other cluster was selected."
            )
        return PrerequisiteResult(
            cli_version=cli_version,
            target_cluster=target,
            auto_selected=auto_selected,
        )

    def collect(
        self,
        prerequisite: PrerequisiteResult,
        *,
        collected_at: datetime | None = None,
    ) -> CollectionResult:
        now = (collected_at or datetime.now(UTC)).astimezone(UTC)
        target = prerequisite.target_cluster
        limitations: list[str] = []

        cluster = None
        cluster_output: str | None = None
        try:
            cluster_output = self.runner.run(
                Operation.GET_CLUSTER_INFO,
                cluster_name=target,
            ).stdout
            cluster = parse_cluster_info(cluster_output, collected_at=now)
        except ReliabilityCommandError:
            limitations.append(
                "Cluster information was unavailable with the current ccloud permissions."
            )
        except OutputParseError:
            limitations.append(
                "Cluster information used an unrecognized output format."
            )

        backup = None
        try:
            config_output = self.runner.run(
                Operation.GET_BACKUP_CONFIG,
                cluster_name=target,
            ).stdout
            backups_output = self.runner.run(
                Operation.LIST_BACKUPS,
                cluster_name=target,
            ).stdout
            backup = parse_backup_health(
                config_output,
                backups_output,
                collected_at=now,
            )
        except ReliabilityCommandError:
            limitations.append(
                "Managed backup information was unavailable with the current "
                "ccloud permissions or cluster plan."
            )
        except OutputParseError:
            limitations.append(
                "Managed backup information used an unrecognized output format."
            )

        restore = None
        try:
            restores_output = self.runner.run(
                Operation.LIST_RESTORES,
                cluster_name=target,
            ).stdout
            restore = parse_restore_health(restores_output, collected_at=now)
        except ReliabilityCommandError:
            limitations.append(
                "Restore history was unavailable with the current ccloud "
                "permissions or cluster plan."
            )
        except OutputParseError:
            limitations.append(
                "Restore history used an unrecognized output format."
            )

        version = None
        try:
            versions_output = self.runner.run(
                Operation.LIST_SUPPORTED_VERSIONS
            ).stdout
            version = parse_version_health(
                versions_output,
                running_version=(
                    cluster.cockroachdb_version if cluster is not None else None
                ),
                collected_at=now,
            )
        except ReliabilityCommandError:
            limitations.append(
                "CockroachDB version support data was unavailable with the "
                "current ccloud permissions."
            )
        except OutputParseError:
            limitations.append(
                "CockroachDB version support data used an unrecognized output format."
            )

        return CollectionResult(
            cli_version=prerequisite.cli_version,
            cluster=cluster,
            backup=backup,
            restore=restore,
            version=version,
            commands_used=self.runner.history,
            limitations=tuple(limitations),
        )
