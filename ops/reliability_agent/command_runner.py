from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ops.reliability_agent.models import CommandResult, Operation


DEFAULT_TIMEOUT_SECONDS = 20
MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 60
MAX_OUTPUT_CHARACTERS = 1_000_000
_CLUSTER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
_CLUSTER_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_STATIC_ARGUMENTS: Mapping[Operation, tuple[str, ...]] = {
    Operation.GET_CLI_VERSION: ("version",),
    Operation.GET_AUTHENTICATED_IDENTITY_STATUS: ("auth", "whoami"),
    Operation.LIST_CLUSTERS: ("cluster", "list"),
    Operation.LIST_SUPPORTED_VERSIONS: ("cluster", "versions"),
}

_CLUSTER_ARGUMENTS: Mapping[Operation, tuple[str, ...]] = {
    Operation.GET_CLUSTER_INFO: ("cluster", "info"),
    Operation.GET_BACKUP_CONFIG: ("cluster", "backup", "config", "get"),
    Operation.LIST_BACKUPS: ("cluster", "backup", "list"),
    Operation.LIST_RESTORES: ("cluster", "restore", "list"),
}


class ReliabilityCommandError(RuntimeError):
    """A safe command failure that never includes raw process output."""


class CCloudNotInstalled(ReliabilityCommandError):
    pass


class CCloudExecutionFailure(ReliabilityCommandError):
    def __init__(self, operation: Operation) -> None:
        super().__init__(
            "The ccloud executable was found, but the read-only operation "
            f"{operation.value!r} could not be started."
        )
        self.operation = operation


class CCloudTimeout(ReliabilityCommandError):
    pass


class CCloudNonzeroExit(ReliabilityCommandError):
    def __init__(self, operation: Operation, return_code: int) -> None:
        super().__init__(
            f"The read-only ccloud operation {operation.value!r} failed "
            f"with exit code {return_code}."
        )
        self.operation = operation
        self.return_code = return_code


class CCloudOutputTooLarge(ReliabilityCommandError):
    pass


class InvalidClusterName(ValueError):
    pass


@dataclass(frozen=True)
class _CompletedProcess:
    returncode: int
    stdout: str
    stderr: str


ProcessRunner = Callable[..., subprocess.CompletedProcess[str] | _CompletedProcess]


def validate_cluster_name(value: str) -> str:
    cleaned = value.strip()
    if (
        cleaned != value
        or not _CLUSTER_NAME.fullmatch(cleaned)
        or _CLUSTER_ID.fullmatch(cleaned)
    ):
        raise InvalidClusterName(
            "The configured ccloud cluster name is invalid. Use only letters, "
            "numbers, dots, underscores, and hyphens; a leading hyphen, "
            "whitespace, command fragment, or Cluster ID is not allowed."
        )
    return cleaned


def _safe_environment(source: Mapping[str, str]) -> dict[str, str]:
    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "TERM",
    }
    return {key: value for key, value in source.items() if key.upper() in allowed}


class CCloudCommandRunner:
    """Run only fixed, read-only ccloud operations without a shell."""

    def __init__(
        self,
        *,
        process_runner: ProcessRunner = subprocess.run,
    ) -> None:
        discovered = shutil.which("ccloud")
        self._executable = self._normalize_executable(discovered)
        self._process_runner = process_runner
        self._history: list[Operation] = []

    @staticmethod
    def _normalize_executable(discovered: str | None) -> str | None:
        if discovered is None:
            return None
        candidate = Path(discovered)
        try:
            return str(candidate.resolve())
        except (OSError, RuntimeError):
            return str(candidate.absolute())

    @property
    def history(self) -> tuple[Operation, ...]:
        return tuple(self._history)

    def arguments_for(
        self,
        operation: Operation,
        *,
        cluster_name: str | None = None,
    ) -> tuple[str, ...]:
        if not isinstance(operation, Operation):
            raise TypeError("operation must be an Operation enum value")
        executable = self._executable
        if executable is None:
            raise CCloudNotInstalled(
                "The ccloud executable was not found in the parent Python "
                "process PATH."
            )
        if operation in _STATIC_ARGUMENTS:
            if cluster_name is not None:
                raise ValueError("This operation does not accept a cluster name.")
            return (executable, *_STATIC_ARGUMENTS[operation])
        if operation in _CLUSTER_ARGUMENTS:
            if cluster_name is None:
                raise ValueError("This operation requires the configured cluster name.")
            validated = validate_cluster_name(cluster_name)
            return (executable, *_CLUSTER_ARGUMENTS[operation], validated)
        raise ValueError("The requested operation is not allowlisted.")

    def run(
        self,
        operation: Operation,
        *,
        cluster_name: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> CommandResult:
        if not MIN_TIMEOUT_SECONDS <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"timeout_seconds must be between {MIN_TIMEOUT_SECONDS} "
                f"and {MAX_TIMEOUT_SECONDS}."
            )
        arguments: Sequence[str] = self.arguments_for(
            operation,
            cluster_name=cluster_name,
        )
        self._history.append(operation)
        try:
            completed = self._process_runner(
                list(arguments),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                env=_safe_environment(os.environ),
            )
        except OSError as error:
            raise CCloudExecutionFailure(
                operation
            ) from error
        except subprocess.TimeoutExpired as error:
            raise CCloudTimeout(
                f"The read-only ccloud operation {operation.value!r} timed out."
            ) from error

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if (
            len(stdout) > MAX_OUTPUT_CHARACTERS
            or len(stderr) > MAX_OUTPUT_CHARACTERS
        ):
            raise CCloudOutputTooLarge(
                f"The read-only ccloud operation {operation.value!r} "
                "returned more output than the safety limit."
            )
        if completed.returncode != 0:
            raise CCloudNonzeroExit(operation, completed.returncode)
        return CommandResult(
            operation=operation,
            stdout=stdout,
            return_code=completed.returncode,
        )
