from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ops.reliability_agent.cli import EXIT_CODES, main, run_check
from ops.reliability_agent.collectors import (
    NoAccessibleClusters,
    PrerequisiteResult,
    ReliabilityCollector,
    TargetClusterNotConfigured,
    TargetClusterNotFound,
    TargetClusterSelectionFailed,
)
from ops.reliability_agent.command_runner import (
    CCloudCommandRunner,
    CCloudExecutionFailure,
    CCloudNonzeroExit,
    CCloudNotInstalled,
    CCloudOutputTooLarge,
    CCloudTimeout,
    InvalidClusterName,
    validate_cluster_name,
)
from ops.reliability_agent.health_rules import (
    evaluate_backup_configuration,
    evaluate_backup_freshness,
    evaluate_cluster,
    evaluate_restores,
    evaluate_version,
    overall_status,
)
from ops.reliability_agent.models import (
    BackupHealthInput,
    ClusterHealthInput,
    CollectionResult,
    HealthCheck,
    HealthStatus,
    Operation,
    RestoreHealthInput,
    VersionHealthInput,
)
from ops.reliability_agent.parsers import (
    OutputParseError,
    parse_backup_health,
    parse_cluster_info,
    parse_cluster_names,
    parse_restore_health,
    parse_version_health,
)
from ops.reliability_agent.report_renderer import (
    DATA_ACCESS_STATEMENT,
    build_report,
    render_json,
    render_markdown,
)
from ops.reliability_agent.sanitizer import REDACTED, sanitize_text, sanitize_value


FIXTURES = Path(__file__).parent / "fixtures" / "ccloud"
FAKE_CCLOUD = str((FIXTURES / "ccloud.exe").resolve())
NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def completed(
    stdout: str = "",
    *,
    stderr: str = "",
    returncode: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
    )


def healthy_collection() -> CollectionResult:
    cluster = parse_cluster_info(
        fixture("cluster-info-ready.txt"),
        collected_at=NOW,
    )
    backup = parse_backup_health(
        fixture("backup-config-enabled.txt"),
        fixture("backups-fresh.txt"),
        collected_at=NOW,
    )
    restore = parse_restore_health(
        fixture("restores-success.txt"),
        collected_at=NOW,
    )
    version = parse_version_health(
        fixture("versions.txt"),
        running_version=cluster.cockroachdb_version,
        collected_at=NOW,
    )
    return CollectionResult(
        cli_version="v1.2.3",
        cluster=cluster,
        backup=backup,
        restore=restore,
        version=version,
        commands_used=tuple(Operation),
    )


def current_healthy_collection() -> CollectionResult:
    current = datetime.now(UTC)
    base = healthy_collection()
    assert base.backup is not None
    assert base.version is not None
    return replace(
        base,
        backup=replace(
            base.backup,
            latest_backup_time=current - timedelta(minutes=10),
            collected_at=current,
        ),
        version=replace(
            base.version,
            support_end=current + timedelta(days=120),
            collected_at=current,
        ),
    )


class CommandRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.which_patcher = patch(
            "ops.reliability_agent.command_runner.shutil.which",
            return_value=FAKE_CCLOUD,
        )
        self.which_patcher.start()
        self.addCleanup(self.which_patcher.stop)

    def test_only_allowlisted_operations_map_to_fixed_arguments(self) -> None:
        runner = CCloudCommandRunner(process_runner=lambda *_args, **_kwargs: completed())
        self.assertEqual(
            runner.arguments_for(Operation.GET_CLI_VERSION),
            (FAKE_CCLOUD, "version"),
        )
        self.assertEqual(
            runner.arguments_for(
                Operation.GET_BACKUP_CONFIG,
                cluster_name="agentbook-primary",
            ),
            (
                FAKE_CCLOUD,
                "cluster",
                "backup",
                "config",
                "get",
                "agentbook-primary",
            ),
        )
        self.assertFalse(hasattr(runner, "run_command"))

    def test_shell_execution_is_disabled(self) -> None:
        observed: dict[str, object] = {}

        def fake(args: list[str], **kwargs: object) -> SimpleNamespace:
            observed["args"] = args
            observed.update(kwargs)
            return completed("ccloud v1.2.3")

        CCloudCommandRunner(process_runner=fake).run(Operation.GET_CLI_VERSION)
        self.assertIs(observed["shell"], False)
        self.assertEqual(observed["args"], [FAKE_CCLOUD, "version"])

    def test_absolute_parent_resolved_executable_is_used(self) -> None:
        observed: dict[str, object] = {}

        def fake(args: list[str], **_kwargs: object) -> SimpleNamespace:
            observed["args"] = args
            return completed("ccloud v1.2.3")

        CCloudCommandRunner(process_runner=fake).run(Operation.GET_CLI_VERSION)
        executable = Path(str(observed["args"][0]))  # type: ignore[index]
        self.assertTrue(executable.is_absolute())
        self.assertEqual(str(executable), FAKE_CCLOUD)

    def test_reduced_child_path_does_not_repeat_executable_discovery(self) -> None:
        observed: dict[str, object] = {}
        runner = CCloudCommandRunner(
            process_runner=lambda args, **kwargs: (
                observed.update({"args": args, "env": kwargs["env"]})
                or completed("ccloud v1.2.3")
            )
        )
        with patch.dict(os.environ, {"PATH": ""}, clear=True):
            runner.run(Operation.GET_CLI_VERSION)
        self.assertEqual(observed["args"], [FAKE_CCLOUD, "version"])
        self.assertEqual(observed["env"], {"PATH": ""})

    def test_arbitrary_command_injection_is_rejected(self) -> None:
        runner = CCloudCommandRunner(process_runner=lambda *_args, **_kwargs: completed())
        with self.assertRaises(InvalidClusterName):
            runner.arguments_for(
                Operation.GET_CLUSTER_INFO,
                cluster_name="prod; cluster delete prod",
            )
        with self.assertRaises(TypeError):
            runner.arguments_for("cluster delete")  # type: ignore[arg-type]

    def test_leading_flag_cluster_name_is_rejected(self) -> None:
        runner = CCloudCommandRunner(process_runner=lambda *_args, **_kwargs: completed())
        with self.assertRaises(InvalidClusterName):
            runner.arguments_for(
                Operation.LIST_BACKUPS,
                cluster_name="--help",
            )

    def test_cluster_id_is_rejected_as_a_public_name(self) -> None:
        with self.assertRaises(InvalidClusterName):
            validate_cluster_name("11111111-1111-4111-8111-111111111111")

    def test_timeouts_fail_safely(self) -> None:
        def timeout(*_args: object, **_kwargs: object) -> SimpleNamespace:
            raise subprocess.TimeoutExpired("ccloud", 5)

        with self.assertRaises(CCloudTimeout):
            CCloudCommandRunner(process_runner=timeout).run(
                Operation.LIST_CLUSTERS
            )

    def test_nonzero_exit_does_not_expose_stderr(self) -> None:
        runner = CCloudCommandRunner(
            process_runner=lambda *_args, **_kwargs: completed(
                stderr="administrator@example.com secret-token",
                returncode=9,
            )
        )
        with self.assertRaises(CCloudNonzeroExit) as context:
            runner.run(Operation.GET_AUTHENTICATED_IDENTITY_STATUS)
        self.assertNotIn("administrator@", str(context.exception))
        self.assertNotIn("secret-token", str(context.exception))

    def test_found_executable_launch_failure_is_not_missing(self) -> None:
        def fail_to_launch(*_args: object, **_kwargs: object) -> SimpleNamespace:
            raise FileNotFoundError("local executable disappeared")

        runner = CCloudCommandRunner(process_runner=fail_to_launch)
        with self.assertRaises(CCloudExecutionFailure) as context:
            runner.run(Operation.GET_CLI_VERSION)
        self.assertNotIsInstance(context.exception, CCloudNotInstalled)
        self.assertNotIn(FAKE_CCLOUD, str(context.exception))

    def test_oversized_output_fails_safely(self) -> None:
        runner = CCloudCommandRunner(
            process_runner=lambda *_args, **_kwargs: completed("x" * 1_000_001)
        )
        with self.assertRaises(CCloudOutputTooLarge):
            runner.run(Operation.LIST_CLUSTERS)

    def test_auth_environment_is_preserved_and_application_secrets_are_excluded(
        self,
    ) -> None:
        observed: dict[str, str] = {}

        def fake(_args: list[str], **kwargs: object) -> SimpleNamespace:
            observed.update(kwargs["env"])  # type: ignore[arg-type]
            return completed("ccloud v1.2.3")

        with patch.dict(
            os.environ,
            {
                "SYSTEMROOT": "C:\\Windows",
                "WINDIR": "C:\\Windows",
                "APPDATA": "C:\\Users\\Test\\AppData\\Roaming",
                "LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local",
                "USERPROFILE": "C:\\Users\\Test",
                "HOME": "C:\\Users\\Test",
                "PATH": "C:\\Windows\\System32",
                "TEMP": "C:\\Temp",
                "TMP": "C:\\Temp",
                "TMPDIR": "C:\\Temp",
                "DATABASE_URL": "postgresql://private",
                "GROQ_API_KEY": "private-groq",
                "OPENAI_API_KEY": "private-openai",
                "LLM_API_KEY": "private-key",
                "GUEST_SESSION_TOKEN_PEPPER": "private-guest-token",
                "SQL_PASSWORD": "private-sql-password",
                "APPLICATION_SIGNING_SECRET": "private-signing-secret",
            },
            clear=True,
        ):
            CCloudCommandRunner(process_runner=fake).run(
                Operation.GET_CLI_VERSION
            )
        for retained in (
            "SYSTEMROOT",
            "WINDIR",
            "APPDATA",
            "LOCALAPPDATA",
            "USERPROFILE",
            "HOME",
            "PATH",
            "TEMP",
            "TMP",
            "TMPDIR",
        ):
            self.assertIn(retained, observed)
        for excluded in (
            "DATABASE_URL",
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
            "LLM_API_KEY",
            "GUEST_SESSION_TOKEN_PEPPER",
            "SQL_PASSWORD",
            "APPLICATION_SIGNING_SECRET",
        ):
            self.assertNotIn(excluded, observed)

    def test_timeout_must_be_bounded(self) -> None:
        runner = CCloudCommandRunner(process_runner=lambda *_args, **_kwargs: completed())
        with self.assertRaises(ValueError):
            runner.run(Operation.LIST_CLUSTERS, timeout_seconds=0)
        with self.assertRaises(ValueError):
            runner.run(Operation.LIST_CLUSTERS, timeout_seconds=61)


class ParserAndRuleTests(unittest.TestCase):
    def test_cluster_names_are_parsed_without_ids(self) -> None:
        names = parse_cluster_names(fixture("cluster-list.txt"))
        self.assertEqual(names, ("agentbook-primary", "agentbook-stage"))
        self.assertNotIn("11111111", repr(names))

    def test_recognized_empty_cluster_lists_parse_as_empty(self) -> None:
        self.assertEqual(parse_cluster_names('{"clusters": []}'), ())
        self.assertEqual(parse_cluster_names("NAME  ID  STATE\n"), ())
        self.assertEqual(parse_cluster_names("No clusters found."), ())

    def test_malformed_cluster_output_is_not_healthy(self) -> None:
        with self.assertRaises(OutputParseError):
            parse_cluster_names("surprising output")
        self.assertEqual(
            evaluate_cluster(None).status,
            HealthStatus.UNKNOWN,
        )

    def test_ready_cluster_maps_to_healthy(self) -> None:
        value = parse_cluster_info(
            fixture("cluster-info-ready.txt"),
            collected_at=NOW,
        )
        self.assertEqual(evaluate_cluster(value).status, HealthStatus.HEALTHY)

    def test_unavailable_cluster_maps_to_critical(self) -> None:
        value = ClusterHealthInput(
            state="CLUSTER_STATE_UNAVAILABLE",
            plan_type=None,
            cloud_provider=None,
            regions=(),
            cockroachdb_version=None,
            resource_limit_or_hardware=None,
            collected_at=NOW,
        )
        self.assertEqual(evaluate_cluster(value).status, HealthStatus.CRITICAL)

    def test_backups_disabled_maps_to_critical(self) -> None:
        value = parse_backup_health(
            fixture("backup-config-disabled.txt"),
            fixture("backups-fresh.txt"),
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_backup_configuration(value).status,
            HealthStatus.CRITICAL,
        )

    def test_fresh_backup_maps_to_healthy(self) -> None:
        value = parse_backup_health(
            fixture("backup-config-enabled.txt"),
            fixture("backups-fresh.txt"),
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_backup_freshness(value, now=NOW).status,
            HealthStatus.HEALTHY,
        )

    def test_stale_backup_maps_to_warning(self) -> None:
        value = parse_backup_health(
            fixture("backup-config-enabled.txt"),
            fixture("backups-stale.txt"),
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_backup_freshness(value, now=NOW).status,
            HealthStatus.WARNING,
        )

    def test_missing_backup_data_maps_to_unknown(self) -> None:
        value = BackupHealthInput(
            enabled=True,
            frequency_minutes=None,
            retention_days=None,
            latest_backup_time=NOW,
            latest_backup_status="COMPLETE",
            backup_count_observed=1,
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_backup_configuration(value).status,
            HealthStatus.UNKNOWN,
        )
        self.assertEqual(
            evaluate_backup_freshness(value, now=NOW).status,
            HealthStatus.UNKNOWN,
        )

    def test_failed_latest_backup_maps_to_critical(self) -> None:
        value = BackupHealthInput(
            enabled=True,
            frequency_minutes=60,
            retention_days=30,
            latest_backup_time=NOW - timedelta(minutes=20),
            latest_backup_status="FAILED",
            backup_count_observed=1,
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_backup_freshness(value, now=NOW).status,
            HealthStatus.CRITICAL,
        )

    def test_failed_restore_maps_to_warning(self) -> None:
        value = parse_restore_health(
            fixture("restores-failed.txt"),
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_restores(value, now=NOW).status,
            HealthStatus.WARNING,
        )

    def test_pending_restore_threshold_maps_to_warning(self) -> None:
        value = parse_restore_health(
            fixture("restores-pending-old.txt"),
            collected_at=NOW,
        )
        check = evaluate_restores(value, now=NOW)
        self.assertEqual(check.status, HealthStatus.WARNING)
        self.assertIn("6-hour", check.summary)

    def test_recent_pending_restore_is_not_a_warning(self) -> None:
        value = RestoreHealthInput(
            total_restore_count=1,
            failed_count=0,
            pending_count=1,
            incomplete_count=0,
            latest_restore_time=NOW - timedelta(hours=1),
            latest_restore_status="PENDING",
            oldest_open_restore_time=NOW - timedelta(hours=1),
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_restores(value, now=NOW).status,
            HealthStatus.HEALTHY,
        )

    def test_no_restores_maps_to_healthy(self) -> None:
        value = parse_restore_health(
            "No restores found.",
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_restores(value, now=NOW).status,
            HealthStatus.HEALTHY,
        )

    def test_supported_version_maps_to_healthy(self) -> None:
        value = parse_version_health(
            fixture("versions.txt"),
            running_version="v25.2.4",
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_version(value, now=NOW).status,
            HealthStatus.HEALTHY,
        )

    def test_unsupported_version_maps_to_critical(self) -> None:
        value = parse_version_health(
            fixture("versions.txt"),
            running_version="v24.3.18",
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_version(value, now=NOW).status,
            HealthStatus.CRITICAL,
        )

    def test_nearing_support_end_maps_to_warning(self) -> None:
        value = parse_version_health(
            fixture("versions.txt"),
            running_version="v25.1.9",
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_version(value, now=NOW).status,
            HealthStatus.WARNING,
        )

    def test_unmatched_version_maps_to_unknown(self) -> None:
        value = parse_version_health(
            fixture("versions.txt"),
            running_version="v23.1.0",
            collected_at=NOW,
        )
        self.assertEqual(
            evaluate_version(value, now=NOW).status,
            HealthStatus.UNKNOWN,
        )

    def test_overall_status_uses_highest_severity(self) -> None:
        checks = (
            HealthCheck("a", "A", HealthStatus.HEALTHY, "ok"),
            HealthCheck("b", "B", HealthStatus.WARNING, "warn"),
            HealthCheck("c", "C", HealthStatus.UNKNOWN, "unknown"),
        )
        self.assertEqual(overall_status(checks), HealthStatus.WARNING)
        critical = checks + (
            HealthCheck("d", "D", HealthStatus.CRITICAL, "critical"),
        )
        self.assertEqual(overall_status(critical), HealthStatus.CRITICAL)


class SanitizerAndReportTests(unittest.TestCase):
    def test_sanitizer_masks_identifiers_email_url_and_path(self) -> None:
        raw = (
            "11111111-1111-4111-8111-111111111111 "
            "administrator@example.com "
            "postgresql://user:pass@private.cockroachlabs.cloud:26257/defaultdb "
            "C:\\Users\\Admin\\auth.json"
        )
        safe = sanitize_text(raw)
        self.assertNotIn("11111111", safe)
        self.assertNotIn("administrator@", safe)
        self.assertNotIn("postgresql://", safe)
        self.assertNotIn("C:\\Users", safe)
        self.assertIn(REDACTED, safe)

    def test_sanitizer_masks_high_entropy_secret(self) -> None:
        secret = "AbCdEfGhIjKlMnOpQrStUvWxYz_123456789"
        self.assertEqual(sanitize_text(secret), REDACTED)

    def test_recursive_sanitizer_drops_sensitive_keys(self) -> None:
        safe = sanitize_value(
            {
                "cluster_id": "private",
                "backup_id": "private",
                "email": "private@example.com",
                "status": "healthy",
            }
        )
        self.assertEqual(safe, {"status": "healthy"})

    def test_reports_contain_no_infrastructure_identifiers(self) -> None:
        report = build_report(healthy_collection(), generated_at=NOW)
        combined = render_json(report) + render_markdown(report)
        for forbidden in (
            "11111111-1111-4111-8111-111111111111",
            "33333333-3333-4333-8333-333333333333",
            "55555555-5555-4555-8555-555555555555",
            "agentbook-primary",
            "administrator@example.com",
            "cockroachlabs.cloud",
        ):
            self.assertNotIn(forbidden, combined)

    def test_reports_contain_no_raw_output_or_learner_content(self) -> None:
        report = build_report(healthy_collection(), generated_at=NOW)
        combined = render_json(report) + render_markdown(report)
        self.assertNotIn("raw_stdout", combined)
        self.assertNotIn("raw_stderr", combined)
        self.assertNotIn("photosynthesis is converted", combined)
        self.assertIn(DATA_ACCESS_STATEMENT, combined)

    def test_json_and_markdown_reports_agree(self) -> None:
        report = build_report(healthy_collection(), generated_at=NOW)
        payload = json.loads(render_json(report))
        markdown = render_markdown(report)
        self.assertEqual(payload["overall_status"], "healthy")
        self.assertIn("**Overall status: HEALTHY**", markdown)
        for check in payload["checks"]:
            self.assertIn(f"**Status: {check['status'].upper()}**", markdown)


class CollectorAndCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.which_patcher = patch(
            "ops.reliability_agent.command_runner.shutil.which",
            return_value=FAKE_CCLOUD,
        )
        self.which_patcher.start()
        self.addCleanup(self.which_patcher.stop)

    def test_one_cluster_is_auto_selected(self) -> None:
        outputs = iter(
            (
                completed("ccloud v1.2.3"),
                completed("authenticated"),
                completed(
                    "NAME               ID                                    STATE\n"
                    "agentbook-primary  11111111-1111-4111-8111-111111111111  "
                    "CLUSTER_STATE_CREATED\n"
                ),
            )
        )
        runner = CCloudCommandRunner(
            process_runner=lambda *_args, **_kwargs: next(outputs)
        )
        prerequisite = ReliabilityCollector(runner).verify_prerequisites(None)
        self.assertEqual(prerequisite.target_cluster, "agentbook-primary")
        self.assertTrue(prerequisite.auto_selected)
        self.assertNotIn(Operation.GET_CLUSTER_INFO, runner.history)

    def test_multiple_clusters_require_explicit_selection(self) -> None:
        outputs = iter(
            (
                completed("ccloud v1.2.3"),
                completed("authenticated"),
                completed(fixture("cluster-list.txt")),
            )
        )
        runner = CCloudCommandRunner(
            process_runner=lambda *_args, **_kwargs: next(outputs)
        )
        collector = ReliabilityCollector(runner)
        with self.assertRaises(TargetClusterNotConfigured) as context:
            collector.verify_prerequisites(None)
        self.assertEqual(
            context.exception.available_names,
            ("agentbook-primary", "agentbook-stage"),
        )
        self.assertNotIn(Operation.GET_CLUSTER_INFO, runner.history)

    def test_zero_clusters_are_rejected(self) -> None:
        outputs = iter(
            (
                completed("ccloud v1.2.3"),
                completed("authenticated"),
                completed("NAME  ID  STATE\n"),
            )
        )
        runner = CCloudCommandRunner(
            process_runner=lambda *_args, **_kwargs: next(outputs)
        )
        with self.assertRaises(NoAccessibleClusters):
            ReliabilityCollector(runner).verify_prerequisites(None)
        self.assertNotIn(Operation.GET_CLUSTER_INFO, runner.history)

    def test_explicit_missing_target_never_falls_back(self) -> None:
        outputs = iter(
            (
                completed("ccloud v1.2.3"),
                completed("authenticated"),
                completed(
                    "NAME               ID                                    STATE\n"
                    "only-safe-cluster  11111111-1111-4111-8111-111111111111  "
                    "CLUSTER_STATE_CREATED\n"
                ),
            )
        )
        runner = CCloudCommandRunner(
            process_runner=lambda *_args, **_kwargs: next(outputs)
        )
        with self.assertRaises(TargetClusterNotFound):
            ReliabilityCollector(runner).verify_prerequisites("missing-cluster")
        self.assertNotIn(Operation.GET_CLUSTER_INFO, runner.history)

    def test_collector_uses_all_read_only_operations(self) -> None:
        mapping = {
            (FAKE_CCLOUD, "version"): "ccloud v1.2.3",
            (FAKE_CCLOUD, "auth", "whoami"): "authenticated",
            (FAKE_CCLOUD, "cluster", "list"): fixture("cluster-list.txt"),
            (
                FAKE_CCLOUD,
                "cluster",
                "info",
                "agentbook-primary",
            ): fixture("cluster-info-ready.txt"),
            (
                FAKE_CCLOUD,
                "cluster",
                "backup",
                "config",
                "get",
                "agentbook-primary",
            ): fixture("backup-config-enabled.txt"),
            (
                FAKE_CCLOUD,
                "cluster",
                "backup",
                "list",
                "agentbook-primary",
            ): fixture("backups-fresh.txt"),
            (
                FAKE_CCLOUD,
                "cluster",
                "restore",
                "list",
                "agentbook-primary",
            ): fixture("restores-success.txt"),
            (FAKE_CCLOUD, "cluster", "versions"): fixture("versions.txt"),
        }

        def fake(args: list[str], **_kwargs: object) -> SimpleNamespace:
            return completed(mapping[tuple(args)])

        collector = ReliabilityCollector(CCloudCommandRunner(process_runner=fake))
        prerequisite = collector.verify_prerequisites("agentbook-primary")
        result = collector.collect(prerequisite, collected_at=NOW)
        self.assertEqual(set(result.commands_used), set(Operation))
        self.assertEqual(build_report(result, generated_at=NOW).overall_status, HealthStatus.HEALTHY)

    def test_shutil_which_success_allows_cli_to_proceed(self) -> None:
        mapping = {
            (FAKE_CCLOUD, "version"): "ccloud v1.2.3",
            (FAKE_CCLOUD, "auth", "whoami"): "authenticated",
            (FAKE_CCLOUD, "cluster", "list"): fixture("cluster-list.txt"),
            (
                FAKE_CCLOUD,
                "cluster",
                "info",
                "agentbook-primary",
            ): fixture("cluster-info-ready.txt"),
            (
                FAKE_CCLOUD,
                "cluster",
                "backup",
                "config",
                "get",
                "agentbook-primary",
            ): fixture("backup-config-enabled.txt"),
            (
                FAKE_CCLOUD,
                "cluster",
                "backup",
                "list",
                "agentbook-primary",
            ): fixture("backups-fresh.txt"),
            (
                FAKE_CCLOUD,
                "cluster",
                "restore",
                "list",
                "agentbook-primary",
            ): fixture("restores-success.txt"),
            (FAKE_CCLOUD, "cluster", "versions"): fixture("versions.txt"),
        }

        def fake(args: list[str], **_kwargs: object) -> SimpleNamespace:
            return completed(mapping[tuple(args)])

        collector = ReliabilityCollector(
            CCloudCommandRunner(process_runner=fake)
        )
        with tempfile.TemporaryDirectory() as directory:
            exit_code = run_check(
                collector=collector,
                output_directory=Path(directory),
                cluster_name="agentbook-primary",
                environment={"PATH": ""},
            )
            combined = (
                (Path(directory) / "latest-report.json").read_text(encoding="utf-8")
                + (Path(directory) / "latest-report.md").read_text(encoding="utf-8")
            )
        self.assertIn(exit_code, {0, 1})
        self.assertNotIn(FAKE_CCLOUD, combined)

    def test_missing_executable_returns_configuration_exit_code(self) -> None:
        with patch(
            "ops.reliability_agent.command_runner.shutil.which",
            return_value=None,
        ):
            collector = ReliabilityCollector(
                CCloudCommandRunner(
                    process_runner=lambda *_args, **_kwargs: self.fail(
                        "a missing executable must fail before subprocess launch"
                    )
                )
            )
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = run_check(collector=collector, environment={})
        self.assertEqual(exit_code, 3)
        self.assertIn("executable was not found", stdout.getvalue())

    def test_execution_failure_is_distinct_from_missing_executable(self) -> None:
        def fail_to_launch(*_args: object, **_kwargs: object) -> SimpleNamespace:
            raise PermissionError("execution blocked")

        collector = ReliabilityCollector(
            CCloudCommandRunner(process_runner=fail_to_launch)
        )
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = run_check(collector=collector, environment={})
        rendered = stdout.getvalue()
        self.assertEqual(exit_code, 3)
        self.assertIn("was found, but it failed to start", rendered)
        self.assertNotIn("was not found", rendered)
        self.assertNotIn(FAKE_CCLOUD, rendered)

    def test_cluster_selection_command_failure_is_distinct(self) -> None:
        outputs = iter(
            (
                completed("ccloud v1.2.3"),
                completed("authenticated"),
                completed(returncode=5),
            )
        )
        collector = ReliabilityCollector(
            CCloudCommandRunner(
                process_runner=lambda *_args, **_kwargs: next(outputs)
            )
        )
        with self.assertRaises(TargetClusterSelectionFailed):
            collector.verify_prerequisites(None)

    def test_public_cli_does_not_accept_an_executable_path(self) -> None:
        with patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                main(
                    [
                        "check",
                        "--ccloud-path",
                        FAKE_CCLOUD,
                    ]
                )

    def test_cli_exit_codes_match_statuses(self) -> None:
        self.assertEqual(EXIT_CODES[HealthStatus.HEALTHY], 0)
        self.assertEqual(EXIT_CODES[HealthStatus.WARNING], 1)
        self.assertEqual(EXIT_CODES[HealthStatus.CRITICAL], 2)
        self.assertEqual(EXIT_CODES[HealthStatus.UNKNOWN], 3)

    def test_cli_writes_sanitized_reports_and_returns_healthy(self) -> None:
        class FakeCollector:
            def verify_prerequisites(
                self,
                _target: str | None,
            ) -> PrerequisiteResult:
                return PrerequisiteResult("v1.2.3", "agentbook-primary")

            def collect(
                self,
                _prerequisite: PrerequisiteResult,
            ) -> CollectionResult:
                return current_healthy_collection()

        with tempfile.TemporaryDirectory() as directory:
            exit_code = run_check(
                collector=FakeCollector(),  # type: ignore[arg-type]
                output_directory=Path(directory),
                cluster_name="agentbook-primary",
            )
            self.assertEqual(exit_code, 0)
            payload = (Path(directory) / "latest-report.json").read_text(
                encoding="utf-8"
            )
            markdown = (Path(directory) / "latest-report.md").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("agentbook-primary", payload + markdown)
            self.assertIn(DATA_ACCESS_STATEMENT, payload + markdown)

    def test_multiple_clusters_return_exit_code_three_and_render_no_ids(self) -> None:
        outputs = iter(
            (
                completed("ccloud v1.2.3"),
                completed("authenticated"),
                completed(fixture("cluster-list.txt")),
            )
        )
        collector = ReliabilityCollector(
            CCloudCommandRunner(
                process_runner=lambda *_args, **_kwargs: next(outputs)
            )
        )
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = run_check(
                collector=collector,
                environment={},
            )
        rendered = stdout.getvalue()
        self.assertEqual(exit_code, 3)
        self.assertIn("agentbook-primary", rendered)
        self.assertIn("agentbook-stage", rendered)
        self.assertNotIn("11111111", rendered)
        self.assertNotIn("22222222", rendered)

    def test_zero_clusters_return_configuration_exit_code(self) -> None:
        outputs = iter(
            (
                completed("ccloud v1.2.3"),
                completed("authenticated"),
                completed('{"clusters": []}'),
            )
        )
        collector = ReliabilityCollector(
            CCloudCommandRunner(
                process_runner=lambda *_args, **_kwargs: next(outputs)
            )
        )
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = run_check(
                collector=collector,
                environment={},
            )
        self.assertEqual(exit_code, 3)
        self.assertIn(
            "No accessible CockroachDB Cloud cluster was found.",
            stdout.getvalue(),
        )

    def test_cli_cluster_name_overrides_environment(self) -> None:
        class RecordingCollector:
            received_target: str | None = None

            def verify_prerequisites(
                self,
                target: str | None,
            ) -> PrerequisiteResult:
                self.received_target = target
                return PrerequisiteResult("v1.2.3", "cli-cluster")

            def collect(
                self,
                _prerequisite: PrerequisiteResult,
            ) -> CollectionResult:
                return current_healthy_collection()

        collector = RecordingCollector()
        with tempfile.TemporaryDirectory() as directory:
            exit_code = run_check(
                collector=collector,  # type: ignore[arg-type]
                output_directory=Path(directory),
                cluster_name="cli-cluster",
                environment={
                    "AGENTBOOK_CCLOUD_CLUSTER": "environment-cluster",
                },
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(collector.received_target, "cli-cluster")

    def test_invalid_cluster_name_is_rejected_by_cli_path(self) -> None:
        class ValidatingCollector:
            collected = False

            def verify_prerequisites(
                self,
                target: str | None,
            ) -> PrerequisiteResult:
                assert target is not None
                validated = validate_cluster_name(target)
                return PrerequisiteResult("v1.2.3", validated)

            def collect(
                self,
                _prerequisite: PrerequisiteResult,
            ) -> CollectionResult:
                self.collected = True
                return current_healthy_collection()

        collector = ValidatingCollector()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = run_check(
                collector=collector,  # type: ignore[arg-type]
                cluster_name="prod; cluster delete prod",
                yes=True,
                input_function=lambda _prompt: self.fail(
                    "--yes must not invoke confirmation"
                ),
            )
        self.assertEqual(exit_code, 3)
        self.assertFalse(collector.collected)
        self.assertNotIn("cluster delete", stdout.getvalue())

    def test_auto_selection_requires_local_confirmation(self) -> None:
        class AutoSelectingCollector:
            collected = False

            def verify_prerequisites(
                self,
                target: str | None,
            ) -> PrerequisiteResult:
                self.assert_target_is_missing(target)
                return PrerequisiteResult(
                    "v1.2.3",
                    "only-safe-cluster",
                    auto_selected=True,
                )

            @staticmethod
            def assert_target_is_missing(target: str | None) -> None:
                if target is not None:
                    raise AssertionError("auto-selection should receive no target")

            def collect(
                self,
                _prerequisite: PrerequisiteResult,
            ) -> CollectionResult:
                self.collected = True
                return current_healthy_collection()

        collector = AutoSelectingCollector()
        stdout = io.StringIO()
        prompts: list[str] = []

        def decline(prompt: str) -> str:
            prompts.append(prompt)
            return "no"

        with redirect_stdout(stdout):
            exit_code = run_check(
                collector=collector,  # type: ignore[arg-type]
                environment={},
                input_function=decline,
            )
        self.assertEqual(exit_code, 3)
        self.assertFalse(collector.collected)
        self.assertEqual(len(prompts), 1)
        self.assertIn("only-safe-cluster", prompts[0])
        self.assertIn("Automatically selected", stdout.getvalue())

    def test_yes_skips_only_confirmation_after_validation(self) -> None:
        class AutoSelectingCollector:
            verified = False
            collected = False

            def verify_prerequisites(
                self,
                target: str | None,
            ) -> PrerequisiteResult:
                self.verified = True
                if target is not None:
                    raise AssertionError("auto-selection should receive no target")
                return PrerequisiteResult(
                    "v1.2.3",
                    "only-safe-cluster",
                    auto_selected=True,
                )

            def collect(
                self,
                _prerequisite: PrerequisiteResult,
            ) -> CollectionResult:
                self.collected = True
                return current_healthy_collection()

        collector = AutoSelectingCollector()
        with tempfile.TemporaryDirectory() as directory:
            exit_code = run_check(
                collector=collector,  # type: ignore[arg-type]
                output_directory=Path(directory),
                environment={},
                yes=True,
                input_function=lambda _prompt: self.fail(
                    "--yes must skip only the local confirmation"
                ),
            )
        self.assertEqual(exit_code, 0)
        self.assertTrue(collector.verified)
        self.assertTrue(collector.collected)

    def test_yes_does_not_bypass_cluster_name_validation(self) -> None:
        class ValidatingCollector:
            collected = False

            def verify_prerequisites(
                self,
                target: str | None,
            ) -> PrerequisiteResult:
                assert target is not None
                validated = validate_cluster_name(target)
                return PrerequisiteResult("v1.2.3", validated)

            def collect(
                self,
                _prerequisite: PrerequisiteResult,
            ) -> CollectionResult:
                self.collected = True
                return current_healthy_collection()

        collector = ValidatingCollector()
        cluster_id = "11111111-1111-4111-8111-111111111111"
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = run_check(
                collector=collector,  # type: ignore[arg-type]
                cluster_name=cluster_id,
                yes=True,
                input_function=lambda _prompt: self.fail(
                    "invalid input must fail before confirmation"
                ),
            )
        self.assertEqual(exit_code, 3)
        self.assertFalse(collector.collected)
        self.assertNotIn(cluster_id, stdout.getvalue())

    def test_main_accepts_safe_cluster_name_and_yes(self) -> None:
        with patch(
            "ops.reliability_agent.cli.run_check",
            return_value=0,
        ) as mocked:
            exit_code = main(
                [
                    "check",
                    "--cluster-name",
                    "safe-cluster",
                    "--yes",
                ]
            )
        self.assertEqual(exit_code, 0)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs["cluster_name"], "safe-cluster")
        self.assertIs(mocked.call_args.kwargs["yes"], True)

    def test_configuration_failure_returns_unknown_exit_code(self) -> None:
        class MissingTargetCollector:
            def verify_prerequisites(
                self,
                _target: str | None,
            ) -> PrerequisiteResult:
                raise TargetClusterNotConfigured(("safe-name",))

        exit_code = run_check(
            collector=MissingTargetCollector(),  # type: ignore[arg-type]
            environment={},
        )
        self.assertEqual(exit_code, 3)


if __name__ == "__main__":
    unittest.main()
