# Reliability Agent Implementation

## Outcome

Phase 8C adds a local Admin/Developer CLI that inspects CockroachDB Cloud
infrastructure using only fixed, read-only `ccloud` operations. It is isolated
under `ops/reliability_agent/` and is not imported by learner-facing services.

The deterministic report works without an LLM. No admin endpoint or public UI
was added because Agentbook has Guest Workspace authentication, not an
independent secure administrator authentication boundary.

## Components

- `models.py`: typed operations, collection inputs, checks, and report model.
- `command_runner.py`: fixed command mapping, cluster-name validation,
  `shell=False`, bounded timeout/output, reduced environment, and safe errors.
- `parsers.py`: conservative text-table and defensive JSON parsers.
- `collectors.py`: authentication and exact-target checks plus permission-aware
  collection.
- `health_rules.py`: deterministic availability, backup, restore, version, and
  overall rules.
- `sanitizer.py`: recursive removal of infrastructure identifiers,
  credentials, URLs, SQL hosts, and local paths.
- `report_renderer.py`: matching JSON and judge-readable Markdown reports.
- `cli.py`: the single safe `check` subcommand and documented exit codes.

## Read-only boundary

The caller can select only an `Operation` enum and, when required, one
validated cluster name. No extra flags or command fragments are accepted.
The package has no SQL client and never reads `DATABASE_URL`.

The subprocess receives a reduced environment containing only operating-system
and local CLI session paths. Database, provider, and application secrets are
not inherited.

## Collection behavior

The CLI verifies:

1. `ccloud` version output is recognizable;
2. `ccloud auth whoami` succeeds without retaining identity output;
3. the configured target exactly matches the cluster list;
4. cluster, backup, restore, and version observations can be collected.

Authentication and target selection are prerequisites. Later plan- or
permission-specific failures become component limitations and `unknown`
checks instead of triggering broader access.

## Deterministic decisions

- Available/created cluster states are healthy; transitions warn; failed or
  unavailable states are critical; unrecognized states are unknown.
- Disabled backups are critical.
- Backup freshness tolerance is
  `max(frequency * 2, frequency + 60 minutes)`.
- Missing frequency prevents a freshness claim.
- Failed restores warn. Pending or incomplete restores warn after six hours.
- Supported versions are healthy unless support ends within 90 days.
- Unsupported versions are critical; unmatched versions are unknown.
- Overall status uses `critical > warning > unknown > healthy`.

An unknown component stays visible even when a more severe component controls
the overall status.

## Report privacy

Public output uses `Agentbook CockroachDB Cluster`. It excludes cluster,
organization, backup, and restore IDs; email; auth tokens; API keys; connection
URLs; SQL hosts; local paths; raw process output; database names; and learner
data.

The report states that observing backups does not prove recoverability.

## CLI

```powershell
python -m ops.reliability_agent.cli check
python -m ops.reliability_agent.cli check --output-dir artifacts/reliability
```

Exit codes:

- `0`: healthy
- `1`: warning
- `2`: critical
- `3`: unknown or configuration failure

Generated live reports are local artifacts and are ignored by Git. Sanitized
examples are stored under `docs/`.

## Verification

The fixture suite covers all requested command, parser, rule, sanitizer,
renderer, and exit-code boundaries. It uses mocked subprocess calls and does
not require CockroachDB Cloud.

Verified on 2026-07-28:

- Python `compileall`: passed for `ops` and `tests`;
- targeted Reliability Agent suite: 38 passed;
- complete backend suite: 265 passed, including the new tests, with 6
  opt-in live-database tests skipped;
- frontend regression suite: 82 passed;
- real CLI failure path: exit code 3 with no fallback when `ccloud` was absent.

The live check was not run because `ccloud` is absent and the target variable
is unset. No fallback credential or SQL path was attempted.

## Future scheduled automation

A scheduled reliability check should use the CockroachDB Cloud API with a
least-privilege Service Account and a managed secret. It should not persist a
human `ccloud` browser session. That design requires separate authorization,
secret-management, scheduler, and deployment work and is intentionally outside
Phase 8C.
