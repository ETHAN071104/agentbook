import { useState } from 'react';
import { Download, Plus, RefreshCw, ShieldCheck, ShieldX } from 'lucide-react';

import { apiClient } from '../api/client';
import type { HealthResponse, IntegrityReport } from '../api/types';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  Notice,
  PageHeader,
  SectionHeader,
} from '../components';
import { useApiQuery } from '../hooks';
import { useOptionalGuestSession } from '../guest/GuestSessionProvider';
import { errorMessage, titleCase } from '../utils/format';

export function SystemPage() {
  const guest = useOptionalGuestSession();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const health = useApiQuery<HealthResponse>(
    'system-health',
    (signal) => apiClient.get('/api/health', { signal }),
  );
  const integrity = useApiQuery<IntegrityReport>(
    'system-integrity',
    (signal) => apiClient.get('/api/system/integrity', { signal }),
  );

  const reloadAll = () => {
    apiClient.invalidate({ prefix: '/api/' });
    void Promise.all([health.reload(), integrity.reload()]);
  };

  const downloadExport = async () => {
    setExporting(true);
    setExportError('');
    try {
      const blob = await apiClient.download('/api/system/export');
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'agentbook-study-export.zip';
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setExportError(errorMessage(error));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Advanced"
        title="Settings and diagnostics"
        description="Export your data, start a new study space, or inspect advanced diagnostics."
        actions={
          <Button
            variant="secondary"
            icon={<RefreshCw size={18} aria-hidden="true" />}
            onClick={reloadAll}
            loading={health.isRefreshing || integrity.isRefreshing}
            loadingText="Checking…"
          >
            Check again
          </Button>
        }
      />

      <section aria-labelledby="service-health-title">
        <SectionHeader headingId="service-health-title" title="Service health" />
        {health.isLoading ? <LoadingState message="Checking local services…" /> : null}
        {health.error ? (
          <ErrorState message={errorMessage(health.error)} onRetry={() => void health.reload()} />
        ) : null}
        {health.data ? (
          <div className="metric-grid">
            <Card>
              <p className="metric-label">Application</p>
              <p className="metric-value">v{health.data.version}</p>
              <Badge tone={health.data.status === 'ok' ? 'success' : 'warning'}>
                {titleCase(health.data.status)}
              </Badge>
            </Card>
            <Card>
              <p className="metric-label">Saved study data</p>
              <p className="metric-value">{titleCase(health.data.database.status)}</p>
              <p className="supporting-text">Private data service</p>
            </Card>
            <Card>
              <p className="metric-label">Material search</p>
              <p className="metric-value">
                {health.data.documents_vector_store.collection_present ? 'Available' : 'Ready'}
              </p>
              <p className="supporting-text">Search service</p>
            </Card>
            <Card>
              <p className="metric-label">Guidance service</p>
              <p className="metric-value metric-value--compact">
                Ready
              </p>
              <p className="supporting-text">Credentials remain private</p>
            </Card>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="integrity-title">
        <SectionHeader
          headingId="integrity-title"
          title="Data integrity"
          actions={
            integrity.data ? (
              <Badge tone={integrity.data.passed ? 'success' : 'danger'}>
                {integrity.data.passed ? 'Checks passed' : 'Attention needed'}
              </Badge>
            ) : null
          }
        />
        {integrity.isLoading ? <LoadingState message="Reading integrity records…" /> : null}
        {integrity.error ? (
          <ErrorState
            message={errorMessage(integrity.error)}
            onRetry={() => void integrity.reload()}
          />
        ) : null}
        {integrity.data ? (
          <Card className="integrity-card">
            <div className="integrity-summary">
              {integrity.data.passed ? (
                <ShieldCheck aria-hidden="true" />
              ) : (
                <ShieldX aria-hidden="true" />
              )}
              <div>
                <h3>{integrity.data.passed ? 'Local records are consistent' : 'Issues were found'}</h3>
                <p>
                  {integrity.data.error_count} errors and {integrity.data.warning_count} warnings.
                </p>
              </div>
            </div>
            {integrity.data.issues.length ? (
              <ul className="issue-list">
                {integrity.data.issues.map((issue, index) => (
                  <li key={`${issue.code}-${issue.record_id ?? index}`}>
                    <Badge tone={issue.severity === 'error' ? 'danger' : 'warning'}>
                      {titleCase(issue.severity)}
                    </Badge>
                    <div>
                      <strong>{titleCase(issue.code)}</strong>
                      <p>{issue.message}</p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                compact
                title="No integrity issues"
                description="Saved study records passed the read-only checks."
              />
            )}
          </Card>
        ) : null}
      </section>

      <section aria-labelledby="backup-title">
        <SectionHeader headingId="backup-title" title="Local backup" />
        <Card className="backup-card">
          <div>
            <h3>Export study data</h3>
            <p>
              Download a portable copy of your study data. Secrets and
              temporary records are excluded.
            </p>
          </div>
          <Button
            icon={<Download size={18} aria-hidden="true" />}
            loading={exporting}
            loadingText="Preparing backup…"
            onClick={() => void downloadExport()}
          >
            Download safe backup
          </Button>
        </Card>
        {exportError ? <Notice tone="error">{exportError}</Notice> : null}
        <Notice tone="info">
          Restore is intentionally not included in this local MVP. Keep the downloaded ZIP somewhere
          safe.
        </Notice>
      </section>

      {guest ? (
        <section aria-labelledby="workspace-title">
          <SectionHeader headingId="workspace-title" title="Study space" />
          <Card className="backup-card">
            <div>
              <h3>Start a new private study space</h3>
              <p>
                This browser will switch to a fresh study space. The previous
                study space is not deleted.
              </p>
            </div>
            <Button
              variant="secondary"
              icon={<Plus size={18} aria-hidden="true" />}
              loading={guest.startingNew}
              loadingText="Creating…"
              onClick={() => void guest.startNewStudySpace()}
            >
              Start a new study space
            </Button>
          </Card>
        </section>
      ) : null}
    </div>
  );
}
