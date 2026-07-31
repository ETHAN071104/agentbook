# Agentbook Infrastructure Reliability Report

**Overall status: HEALTHY**

Generated: `2026-07-28T12:00:00+00:00`

Target: **Agentbook CockroachDB Cluster**

## Cluster availability

**Status: HEALTHY**

The target CockroachDB Cloud cluster reports an available state.

- State: CLUSTER_STATE_CREATED
- Plan Type: PLAN_STANDARD
- Cloud Provider: CLOUD_PROVIDER_GCP
- Regions: us-central1
- CockroachDB Version: v25.2.4
- Resource Limit or Hardware: 200

## Managed backup configuration

**Status: HEALTHY**

Managed backups are enabled with visible frequency and retention settings.

- Enabled: Yes
- Frequency Minutes: 60
- Retention Days: 30

## Backup freshness

**Status: HEALTHY**

The latest visible backup is within the configured freshness tolerance.

- Latest Backup Time: 2026-07-28T11:30:00+00:00
- Latest Backup Status: COMPLETE
- Backup Count Observed: 2
- Age Minutes: 30
- Freshness Tolerance Minutes: 120

## Restore status

**Status: HEALTHY**

Managed backups were observed and no failed restore record was found.

- Total Restore Count: 1
- Failed Count: 0
- Pending Count: 0
- Incomplete Count: 0
- Latest Restore Time: 2026-07-20T12:00:00+00:00
- Latest Restore Status: SUCCESS

## Version support

**Status: HEALTHY**

The running CockroachDB major version is marked supported.

- Running Major Version: v25.2
- Support Status: SUPPORTED
- Support End: 2026-11-18
- Support Days Remaining: 112
- Allowed Upgrade Targets: None

## Warnings and recommended actions

- No deterministic warning was produced.

## Privacy boundary

No learner documents, quiz responses, memories, tasks, embeddings, or SQL rows
were accessed during this check.

The agent used only fixed, read-only CockroachDB Cloud infrastructure
operations. It did not use SQL, a database URL, or learner credentials.

## Commands used

- Check ccloud CLI version
- Verify ccloud authentication status
- Validate configured target cluster
- Inspect cluster availability and configuration
- Inspect managed backup configuration
- Inspect managed backup freshness
- Inspect restore-operation status
- Inspect CockroachDB version support

## Collection limitations

- Managed backups were observed and no failed restore record was found. This
  does not prove backup recoverability.
