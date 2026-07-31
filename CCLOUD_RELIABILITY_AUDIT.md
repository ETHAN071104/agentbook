# ccloud Reliability Environment Audit

Audit date: 2026-07-28

Selection UX implementation reviewed: 2026-07-29

## Local result

`ccloud` was not installed or available on `PATH`. Checks of the usual
per-user and program installation locations also found no executable.
Agentbook did not install, upgrade, or download the CLI.

Because the executable is absent:

- installed version: unavailable;
- `ccloud --help`: unavailable;
- `ccloud cluster --help`: unavailable;
- command-specific help: unavailable;
- installed machine-readable formats: unverified;
- authentication state: unknown;
- cluster list: unavailable;
- live read-only smoke test: blocked.

`AGENTBOOK_CCLOUD_CLUSTER` was not configured at audit time. Because `ccloud`
was unavailable, no cluster list could be read and no target was selected.

## Documented read-only command surface

The implementation is restricted to these fixed command arrays:

| Operation | Fixed command |
| --- | --- |
| CLI version | `ccloud version` |
| Authentication status | `ccloud auth whoami` |
| Cluster discovery | `ccloud cluster list` |
| Cluster availability | `ccloud cluster info <configured-name>` |
| Backup configuration | `ccloud cluster backup config get <configured-name>` |
| Backup freshness | `ccloud cluster backup list <configured-name>` |
| Restore status | `ccloud cluster restore list <configured-name>` |
| Version support | `ccloud cluster versions` |

Cockroach Labs' current
[`ccloud` command reference](https://www.cockroachlabs.com/docs/cockroachcloud/ccloud-reference)
documents the cluster, managed-backup, restore-list, and versions command
families. The installed version could not be checked for JSON or another
machine-readable flag, so Phase 8C does not add an unverified output flag.
Parsers conservatively support the documented text tables and defensive JSON
shapes; unrecognized output becomes `unknown`.

## Authentication category

Unknown because the CLI is absent. The Reliability Agent did not inspect an
auth cache, open a browser, or attempt login. After a human administrator
installs `ccloud`, the required flow is:

```powershell
ccloud auth login
ccloud auth whoami
```

The first command is manual and is never automated by Agentbook. The second is
executed only to verify that a valid human session exists. Its output is not
stored or included in a report.

## Target-cluster selection

Selection priority is:

1. `--cluster-name "<exact-name>"`
2. `AGENTBOOK_CCLOUD_CLUSTER`
3. automatic selection only when the authenticated account exposes exactly one
   validated cluster name

Every path first runs the fixed `ccloud cluster list` operation. Explicit names
must match that list exactly and never fall back to another cluster. Cluster
IDs, leading flags, whitespace, and command fragments are rejected as public
input.

For one accessible cluster and no explicit selection, the CLI displays only
its sanitized name and requires local confirmation before cluster-specific
checks. `--yes` skips only that confirmation; it does not skip discovery,
authentication, input validation, or existence validation.

Zero accessible clusters stop with configuration exit code `3`. Multiple
accessible clusters also stop with code `3`, list sanitized names only, and
require one of the two explicit name inputs. The agent never chooses among
multiple clusters.

Public reports always use `Agentbook CockroachDB Cluster`, not the configured
name. Cluster IDs, organization IDs, connection hosts, and administrator
identity are never public report fields.

## Safety findings

- No `ccloud` process ran during this audit because the executable was absent.
- No SQL client, SQL shell, database URL, credential, or learner row was used.
- The process runner accepts an operation enum rather than an arbitrary command.
- It uses fixed arguments, `shell=False`, a bounded timeout, accepted-output
  limits, and a reduced environment that excludes database and LLM secrets.
- Cluster-name validation rejects UUID-shaped Cluster IDs and all values that
  could become flags or command fragments.
- Automatic selection is limited to an exact one-cluster result and is gated
  by a local confirmation unless `--yes` is explicitly supplied.
- Errors do not include raw stdout or stderr.
- Live reports are ignored under `artifacts/reliability/`.

## Plan and permission limitations

Backup and restore visibility can vary by CockroachDB Cloud plan and the
administrator's roles. When the CLI is installed, a command that is absent or
not permitted is reported as unavailable. The agent does not request broader
permissions or update cluster configuration.

The controlled live smoke test remains blocked until `ccloud` is installed and
a human login is valid. An explicit target is required only when more than one
cluster is accessible.
