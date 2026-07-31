# Agentbook Reliability Agent

## Purpose

The Reliability Agent is a local administrator tool for the CockroachDB Cloud
infrastructure that preserves Agentbook learning state. It checks cluster
availability, managed-backup configuration and freshness, restore history, and
CockroachDB major-version support.

It does not assess whether a learner memory is factually correct. It does not
read documents, quiz responses, memories, tasks, embeddings, tokens, or SQL
rows.

## Relationship to Agentbook's CockroachDB integrations

1. **Distributed Vector Indexing** is a runtime learner capability for
   document and learner-memory retrieval.
2. **CockroachDB Cloud Managed MCP** was used during development for read-only
   schema and query validation.
3. **ccloud Reliability Agent** is an administrator/runtime-operations
   inspection tool.

Students do not use `ccloud`.

## Prerequisites

1. Install `ccloud` manually using Cockroach Labs' documentation.
2. Log in as a human administrator:

   ```powershell
   ccloud auth login
   ```

3. Verify the session without copying its output into public evidence:

   ```powershell
   ccloud auth whoami
   ```

4. If the account exposes more than one cluster, configure one exact target
   name:

   ```powershell
   $env:AGENTBOOK_CCLOUD_CLUSTER="exact-cluster-name"
   ```

   Or pass the safe CLI argument:

   ```powershell
   .\.venv\Scripts\python.exe -m ops.reliability_agent.cli check `
     --cluster-name "exact-cluster-name"
   ```

   `--cluster-name` has priority over `AGENTBOOK_CCLOUD_CLUSTER`. Both accept
   only a validated cluster name; Cluster IDs, leading flags, whitespace, and
   command fragments are rejected.

If neither explicit selection is present, the agent runs its fixed,
read-only cluster-list operation. It automatically selects a cluster only when
exactly one valid name is accessible. The sanitized name is shown locally and
the operator must confirm before cluster-specific live checks run.

If no cluster is accessible, the command stops with configuration exit code
`3`. If multiple clusters are accessible, it lists only their sanitized names
and requires `--cluster-name` or `AGENTBOOK_CCLOUD_CLUSTER`.

The CLI never automates browser login, stores an auth token, creates a Service
Account, accepts a Cluster ID as its public target, or chooses among multiple
clusters.

## Run

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m ops.reliability_agent.cli check
```

When the authenticated account exposes exactly one cluster, this prompts:

```text
Automatically selected the only accessible cluster: <sanitized-name>
Run live read-only checks against <sanitized-name>? [y/N]:
```

For a controlled non-interactive demo, `--yes` skips only this local
confirmation:

```powershell
.\.venv\Scripts\python.exe -m ops.reliability_agent.cli check --yes
```

Discovery, exact-name validation, authentication checks, and existence
validation still run with `--yes`.

Optional output directory:

```powershell
.\.venv\Scripts\python.exe -m ops.reliability_agent.cli check `
  --output-dir artifacts/reliability
```

Generated files:

- `artifacts/reliability/latest-report.json`
- `artifacts/reliability/latest-report.md`

The directory is ignored by Git. Inspect both reports before sharing them.

## Fixed operations

The CLI may execute only:

- `ccloud version`
- `ccloud auth whoami`
- `ccloud cluster list`
- `ccloud cluster info <configured-name>`
- `ccloud cluster backup config get <configured-name>`
- `ccloud cluster backup list <configured-name>`
- `ccloud cluster restore list <configured-name>`
- `ccloud cluster versions`

Cluster selection always runs through `ccloud cluster list` before any
cluster-specific operation. An explicit CLI or environment name must match the
validated names returned by that operation; the agent never falls back to a
different cluster.

There is no generic command option, SQL access, restore action, backup update,
cluster update, or resource create/delete operation.

## Health rules

Statuses are `healthy`, `warning`, `critical`, and `unknown`.

- Backup freshness uses
  `max(configured frequency * 2, configured frequency + 60 minutes)`.
- Pending or incomplete restores warn after six hours.
- Version support warns within 90 days of support end.
- Malformed, missing, or newly changed output becomes `unknown`.
- Overall status uses the most severe deterministic component result.

The report does not claim that backup existence guarantees recovery.

## Authentication and permissions

Phase 8C uses the human administrator's existing local session. If
authentication is invalid, run `ccloud auth login` manually. The agent never
falls back to a database URL or SQL credential.

If one read operation is unavailable for the current plan or role, that
component remains unavailable or unknown. Do not grant broader permissions
automatically.

Future scheduled automation should use the CockroachDB Cloud API with a
least-privilege Service Account and managed secrets. It must not persist a
human CLI session.

## Privacy boundary

Reports use a generic cluster display name and exclude raw output, IDs, email,
connection hosts, credentials, local paths, database names, and learner data.

> No learner documents, quiz responses, memories, tasks, embeddings, or SQL
> rows were accessed during this check.

## Current local limitation

At implementation time, `ccloud` was not installed on this workstation and no
live target could be inspected. Fixture tests and sanitized examples are
complete, including zero-, one-, and multiple-cluster selection cases, but the
controlled live smoke test remains blocked.
