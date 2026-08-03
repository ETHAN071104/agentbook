import { useState, type FormEvent } from "react";
import {
  ArrowUpDown,
  CalendarDays,
  FilePlus2,
  FileText,
  FolderInput,
  FolderOpen,
  NotebookTabs,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { Link } from "react-router-dom";

import {
  api,
  getErrorMessage,
  type DocumentRecord,
  type Notebook,
  type NotebookCreate,
  type NotebookUpdate,
  type PublicId,
} from "../api";
import {
  Badge,
  Button,
  Card,
  ConfirmationDialog,
  Dialog,
  EmptyState,
  ErrorState,
  LoadingState,
  Notice,
  PageHeader,
} from "../components";
import { useApiQuery, useAsyncAction } from "../hooks";

interface UpdateNotebookArgs {
  id: PublicId;
  payload: NotebookUpdate;
}

interface UploadDocumentArgs {
  file: File;
  notebookId: PublicId | null;
}

interface AssignDocumentArgs {
  documentId: PublicId;
  notebookId: PublicId | null;
}

type LibrarySort = "newest" | "oldest" | "name";

function notebookValue(notebookId: PublicId | null) {
  return notebookId == null ? "unsorted" : String(notebookId);
}

function parseNotebookValue(value: string) {
  return value === "unsorted" ? null : value;
}

function formatAddedDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function NotebooksPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedNotebookId, setSelectedNotebookId] = useState("unsorted");
  const [sort, setSort] = useState<LibrarySort>("newest");
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [editNotebook, setEditNotebook] = useState<Notebook | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [deleteNotebook, setDeleteNotebook] = useState<Notebook | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [uploadNotebookId, setUploadNotebookId] = useState("unsorted");
  const [assignmentDrafts, setAssignmentDrafts] = useState<Record<PublicId, string>>({});

  const notebooks = useApiQuery(["notebooks", search], (signal) =>
    api.listNotebooks(search || undefined, { signal }),
  );
  const documents = useApiQuery(["documents", search], (signal) =>
    api.listDocuments({ q: search || undefined }, { signal }),
  );
  const notebookOptions = useApiQuery(["notebooks", "assignment-options"], (signal) =>
    api.listNotebooks(undefined, { signal }),
  );

  const createAction = useAsyncAction(
    (payload: NotebookCreate, signal: AbortSignal) => api.createNotebook(payload, { signal }),
  );
  const updateAction = useAsyncAction(
    ({ id, payload }: UpdateNotebookArgs, signal: AbortSignal) =>
      api.updateNotebook(id, payload, { signal }),
  );
  const deleteAction = useAsyncAction((id: PublicId, signal: AbortSignal) =>
    api.deleteNotebook(id, { signal }),
  );
  const uploadAction = useAsyncAction(
    ({ file: selectedFile, notebookId }: UploadDocumentArgs, signal: AbortSignal) =>
      api.uploadDocument(selectedFile, notebookId, { signal }),
  );
  const assignAction = useAsyncAction(
    ({ documentId, notebookId }: AssignDocumentArgs, signal: AbortSignal) =>
      api.assignDocument(documentId, notebookId, { signal }),
  );

  function reloadLibrary() {
    notebooks.reload();
    documents.reload();
    notebookOptions.reload();
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: NotebookCreate = {
      name: createName.trim(),
      description: createDescription.trim() || null,
    };
    if (!payload.name) return;
    try {
      const created = await createAction.run(payload);
      if (!created) return;
      setCreateName("");
      setCreateDescription("");
      setCreateOpen(false);
      setSelectedNotebookId(String(created.id));
      notebooks.reload();
      notebookOptions.reload();
    } catch {
      // Keep the dialog and values available for correction.
    }
  }

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editNotebook?.id || !editName.trim()) return;
    try {
      const updated = await updateAction.run({
        id: editNotebook.id,
        payload: { name: editName.trim(), description: editDescription.trim() },
      });
      if (!updated) return;
      setEditNotebook(null);
      notebooks.reload();
      notebookOptions.reload();
    } catch {
      // Keep the edit form open with user input intact.
    }
  }

  async function handleDelete() {
    if (!deleteNotebook?.id) return;
    try {
      const deleted = await deleteAction.run(deleteNotebook.id);
      if (!deleted) return;
      if (selectedNotebookId === String(deleteNotebook.id)) setSelectedNotebookId("unsorted");
      setDeleteNotebook(null);
      reloadLibrary();
    } catch {
      // Confirmation remains open and exposes the backend reason.
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    try {
      const result = await uploadAction.run({
        file,
        notebookId: parseNotebookValue(uploadNotebookId),
      });
      if (!result) return;
      setFile(null);
      setFileInputKey((value) => value + 1);
      setSelectedNotebookId(uploadNotebookId);
      setUploadOpen(false);
      reloadLibrary();
    } catch {
      // Selected file and target notebook remain set for retry.
    }
  }

  async function handleAssignment(document: DocumentRecord) {
    const draft = assignmentDrafts[document.id] ?? notebookValue(document.notebook_id);
    try {
      const updated = await assignAction.run({
        documentId: document.id,
        notebookId: parseNotebookValue(draft),
      });
      if (!updated) return;
      setAssignmentDrafts((current) => {
        const next = { ...current };
        delete next[document.id];
        return next;
      });
      reloadLibrary();
    } catch {
      // Draft assignment remains selected.
    }
  }

  if (notebooks.isLoading && !notebooks.data) {
    return <LoadingState message="Loading your Library..." />;
  }

  if (notebooks.error && !notebooks.data) {
    return (
      <ErrorState
        title="Library unavailable"
        message={getErrorMessage(notebooks.error)}
        onRetry={notebooks.retry}
      />
    );
  }

  if (!notebooks.data) return null;

  const notebookItems = notebooks.data.items;
  const assignmentNotebooks = notebookOptions.data?.items ?? notebookItems;
  const documentItems = documents.data?.items ?? [];
  const selectedNotebook = assignmentNotebooks.find(
    (notebook) => String(notebook.id) === selectedNotebookId,
  );
  const selectedNotebookName = selectedNotebookId === "all"
    ? "All material"
    : selectedNotebookId === "unsorted"
      ? "Unsorted"
      : selectedNotebook?.name ?? "Notebook";
  const selectedDocuments = documentItems
    .filter((document) => {
      if (selectedNotebookId === "all") return true;
      if (selectedNotebookId === "unsorted") return document.notebook_id == null;
      return String(document.notebook_id) === selectedNotebookId;
    })
    .sort((left, right) => {
      if (sort === "name") return left.filename.localeCompare(right.filename);
      const delta = Date.parse(left.created_at) - Date.parse(right.created_at);
      return sort === "oldest" ? delta : -delta;
    });

  return (
    <div className="page-stack library-page library-page--workspace">
      <PageHeader
        eyebrow="Your material"
        title="My Library"
        description="Find, organize, and study everything you have added to Agentbook."
        actions={
          <div className="button-group">
            <a
              className="button button--primary"
              href="#upload"
              onClick={(event) => {
                event.preventDefault();
                uploadAction.reset();
                setUploadOpen(true);
              }}
            >
              <FilePlus2 size={18} aria-hidden="true" />
              <span>Upload study material</span>
            </a>
            <Button
              variant="secondary"
              icon={<Plus size={18} aria-hidden="true" />}
              onClick={() => {
                createAction.reset();
                setCreateOpen(true);
              }}
            >
              New notebook
            </Button>
          </div>
        }
      />

      <form
        className="search-form library-search library-global-search"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setSearch(searchInput.trim());
        }}
      >
        <label className="visually-hidden" htmlFor="library-search">Search your Library</label>
        <div className="search-form__controls">
          <div className="library-search-field">
            <Search size={20} aria-hidden="true" />
            <input
              id="library-search"
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search notebooks and materials..."
              maxLength={255}
            />
          </div>
          <Button variant="secondary" type="submit">Search</Button>
        </div>
      </form>

      {uploadAction.data ? (
        <Notice
          tone={uploadAction.data.duplicate ? "warning" : "success"}
          title={uploadAction.data.duplicate ? "Material already exists" : "Material is ready"}
        >
          <div className="upload-success library-upload-success">
            <p>
              {uploadAction.data.document.filename}
              {uploadAction.data.duplicate
                ? " is already in your Library."
                : " was uploaded successfully."}
            </p>
            <div className="button-group">
              <Link className="text-link" to="/chat">Ask about this</Link>
              <Link
                className="text-link"
                to={`/study-actions?view=quiz&document_ids=${uploadAction.data.document.id}&scope_name=${encodeURIComponent(uploadAction.data.document.filename)}`}
              >
                Practice this
              </Link>
            </div>
          </div>
        </Notice>
      ) : null}

      <div className="library-workspace">
        <aside className="library-browser" aria-label="Notebooks">
          <div className="library-browser__header">
            <div>
              <p className="eyebrow">Collections</p>
              <h2>Notebooks</h2>
            </div>
            <Badge tone="neutral">{notebookItems.length + 1}</Badge>
          </div>

          {notebooks.isRefreshing ? <LoadingState compact message="Refreshing notebooks..." /> : null}

          <div className="library-notebook-list">
            <div className={selectedNotebookId === "all" ? "library-notebook-item is-active" : "library-notebook-item"}>
              <button
                type="button"
                className="library-notebook-select"
                aria-pressed={selectedNotebookId === "all"}
                onClick={() => setSelectedNotebookId("all")}
              >
                <span className="library-notebook-icon" aria-hidden="true"><NotebookTabs size={20} /></span>
                <span><strong>All material</strong><small>{documentItems.length} sources</small></span>
              </button>
            </div>

            <div className={selectedNotebookId === "unsorted" ? "library-notebook-item is-active" : "library-notebook-item"}>
              <button
                type="button"
                className="library-notebook-select"
                aria-pressed={selectedNotebookId === "unsorted"}
                onClick={() => setSelectedNotebookId("unsorted")}
              >
                <span className="library-notebook-icon" aria-hidden="true"><FolderInput size={20} /></span>
                <span>
                  <strong>Unsorted</strong>
                  <small>{notebooks.data.unsorted.document_count} source{notebooks.data.unsorted.document_count === 1 ? "" : "s"}</small>
                </span>
              </button>
              <Link className="icon-button library-notebook-action" to="/notebooks/unsorted" aria-label="Open Unsorted notebook">
                <FolderOpen size={17} aria-hidden="true" />
              </Link>
            </div>

            {notebookItems.map((notebook) => (
              <div
                key={notebook.id}
                className={selectedNotebookId === String(notebook.id) ? "library-notebook-item is-active" : "library-notebook-item"}
              >
                <button
                  type="button"
                  className="library-notebook-select"
                  aria-pressed={selectedNotebookId === String(notebook.id)}
                  onClick={() => setSelectedNotebookId(String(notebook.id))}
                >
                  <span className="library-notebook-icon" aria-hidden="true"><NotebookTabs size={20} /></span>
                  <span>
                    <strong>{notebook.name}</strong>
                    <small>{notebook.document_count} source{notebook.document_count === 1 ? "" : "s"}</small>
                  </span>
                </button>
                <div className="library-notebook-actions">
                  <Link className="icon-button" to={`/notebooks/${notebook.id}`} aria-label={`Open ${notebook.name} notebook`}>
                    <FolderOpen size={16} aria-hidden="true" />
                  </Link>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Edit ${notebook.name}`}
                    onClick={() => {
                      updateAction.reset();
                      setEditNotebook(notebook);
                      setEditName(notebook.name);
                      setEditDescription(notebook.description);
                    }}
                  >
                    <Pencil size={16} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Delete ${notebook.name}`}
                    disabled={notebook.document_count > 0}
                    title={notebook.document_count > 0 ? "Move every document before deleting" : undefined}
                    onClick={() => {
                      deleteAction.reset();
                      setDeleteNotebook(notebook);
                    }}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {notebookItems.length === 0 && search ? (
            <div className="library-browser__empty">
              <p>No notebooks matched “{search}”.</p>
              <Button variant="ghost" onClick={() => { setSearch(""); setSearchInput(""); }}>Clear search</Button>
            </div>
          ) : null}
        </aside>

        <section className="library-material-panel" aria-labelledby="library-material-title">
          <div className="library-material-panel__header">
            <div>
              <p className="eyebrow">{selectedDocuments.length} source{selectedDocuments.length === 1 ? "" : "s"}</p>
              <h2 id="library-material-title">{selectedNotebookName}</h2>
            </div>
            <label className="library-sort">
              <ArrowUpDown size={17} aria-hidden="true" />
              <span className="visually-hidden">Sort material</span>
              <select value={sort} onChange={(event) => setSort(event.target.value as LibrarySort)}>
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="name">Name</option>
              </select>
            </label>
          </div>

          {documents.isLoading && !documents.data ? (
            <LoadingState message="Loading study material..." />
          ) : documents.error && !documents.data ? (
            <ErrorState
              title="Study material is unavailable"
              message={getErrorMessage(documents.error)}
              onRetry={documents.retry}
            />
          ) : selectedDocuments.length ? (
            <div className="library-document-list">
              {selectedDocuments.map((document) => {
                const actualValue = notebookValue(document.notebook_id);
                const draftValue = assignmentDrafts[document.id] ?? actualValue;
                return (
                  <Card key={document.id} padding="small" className="library-document-card">
                    <div className="library-document-main">
                      <span className="library-document-icon" aria-hidden="true"><FileText size={22} /></span>
                      <div className="library-document-copy">
                        <h3><Link to={`/documents/${document.id}`}>{document.filename}</Link></h3>
                        <div className="library-document-meta">
                          <span>Ready to study</span>
                          <span><CalendarDays size={14} aria-hidden="true" /> Added {formatAddedDate(document.created_at)}</span>
                        </div>
                      </div>
                    </div>

                    <div className="library-document-actions">
                      <Link className="button button--secondary" to="/chat">Ask Agentbook</Link>
                      <Link
                        className="button button--secondary"
                        to={`/study-actions?view=quiz&document_ids=${document.id}&scope_name=${encodeURIComponent(document.filename)}`}
                      >
                        Practice
                      </Link>
                      <Link className="button button--ghost" to={`/documents/${document.id}`}>Details</Link>
                    </div>

                    <div className="library-document-move">
                      <label htmlFor={`assignment-${document.id}`}>Move to</label>
                      <select
                        id={`assignment-${document.id}`}
                        value={draftValue}
                        disabled={assignAction.isPending}
                        onChange={(event) => setAssignmentDrafts((current) => ({ ...current, [document.id]: event.target.value }))}
                      >
                        <option value="unsorted">Unsorted</option>
                        {assignmentNotebooks.map((notebook) => (
                          <option key={notebook.id} value={notebook.id ?? ""}>{notebook.name}</option>
                        ))}
                      </select>
                      {draftValue !== actualValue ? (
                        <Button
                          variant="secondary"
                          icon={<FolderInput size={17} aria-hidden="true" />}
                          disabled={assignAction.isPending}
                          onClick={() => void handleAssignment(document)}
                        >
                          Save move
                        </Button>
                      ) : null}
                    </div>
                  </Card>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title={search ? "No matching material" : `No material in ${selectedNotebookName}`}
              description={search ? `No material matched “${search}”.` : "Upload a source or choose another notebook."}
              icon={<NotebookTabs />}
              action={
                <Button icon={<FilePlus2 size={18} aria-hidden="true" />} onClick={() => setUploadOpen(true)}>
                  Upload material
                </Button>
              }
            />
          )}

          {assignAction.error ? (
            <Notice tone="error" title="Material was not moved">
              {getErrorMessage(assignAction.error)} Your selected destination is preserved.
            </Notice>
          ) : null}
        </section>
      </div>

      <Dialog
        open={uploadOpen}
        onClose={() => {
          if (!uploadAction.isPending) setUploadOpen(false);
        }}
        title="Upload study material"
        description="Add a PDF, text file, or presentation and choose where it belongs."
      >
        <form id="upload" className="library-upload-form" onSubmit={handleUpload}>
          <div className="field-stack">
            <label htmlFor="document-upload">Study material file</label>
            <input
              key={fileInputKey}
              id="document-upload"
              type="file"
              accept=".pdf,.txt,.pptx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.presentationml.presentation"
              required
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                uploadAction.reset();
              }}
              disabled={uploadAction.isPending}
            />
            <p className="field-help">Protected, empty, damaged, unsupported, or oversized files cannot be added.</p>
          </div>
          <div className="field-stack">
            <label htmlFor="upload-notebook">Destination</label>
            <select
              id="upload-notebook"
              value={uploadNotebookId}
              onChange={(event) => setUploadNotebookId(event.target.value)}
              disabled={uploadAction.isPending}
            >
              <option value="unsorted">Unsorted</option>
              {assignmentNotebooks.map((notebook) => (
                <option key={notebook.id} value={notebook.id ?? ""}>{notebook.name}</option>
              ))}
            </select>
          </div>
          <div className="form-actions library-upload-form__actions">
            <Button variant="ghost" onClick={() => setUploadOpen(false)} disabled={uploadAction.isPending}>Cancel</Button>
            <Button
              type="submit"
              loading={uploadAction.isPending}
              loadingText="Preparing material..."
              icon={<FilePlus2 size={18} aria-hidden="true" />}
              disabled={!file}
            >
              Upload study material
            </Button>
          </div>
          {uploadAction.error ? (
            <Notice tone="error" title="Upload failed">
              {getErrorMessage(uploadAction.error)} Choose another file or retry.
            </Notice>
          ) : null}
        </form>
      </Dialog>

      <Dialog
        open={createOpen}
        onClose={() => {
          if (!createAction.isPending) setCreateOpen(false);
        }}
        title="Create notebook"
        description="Add a focused home for related study material."
        actions={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)} disabled={createAction.isPending}>Cancel</Button>
            <Button
              form="create-notebook-form"
              type="submit"
              loading={createAction.isPending}
              loadingText="Creating..."
              disabled={!createName.trim()}
            >
              Create notebook
            </Button>
          </>
        }
      >
        <form id="create-notebook-form" className="field-stack" onSubmit={handleCreate}>
          <label htmlFor="create-notebook-name">Name</label>
          <input
            id="create-notebook-name"
            value={createName}
            onChange={(event) => { setCreateName(event.target.value); createAction.reset(); }}
            disabled={createAction.isPending}
            maxLength={120}
            required
            autoFocus
          />
          <label htmlFor="create-notebook-description">Description</label>
          <textarea
            id="create-notebook-description"
            value={createDescription}
            onChange={(event) => { setCreateDescription(event.target.value); createAction.reset(); }}
            disabled={createAction.isPending}
            maxLength={1000}
            rows={4}
          />
          {createAction.error ? <Notice tone="error">{getErrorMessage(createAction.error)}</Notice> : null}
        </form>
      </Dialog>

      <Dialog
        open={Boolean(editNotebook)}
        onClose={() => {
          if (!updateAction.isPending) setEditNotebook(null);
        }}
        title="Edit notebook"
        actions={
          <>
            <Button variant="ghost" onClick={() => setEditNotebook(null)} disabled={updateAction.isPending}>Cancel</Button>
            <Button
              form="edit-notebook-form"
              type="submit"
              loading={updateAction.isPending}
              loadingText="Saving..."
              disabled={!editName.trim()}
            >
              Save changes
            </Button>
          </>
        }
      >
        <form id="edit-notebook-form" className="field-stack" onSubmit={handleUpdate}>
          <label htmlFor="edit-notebook-name">Name</label>
          <input
            id="edit-notebook-name"
            value={editName}
            onChange={(event) => { setEditName(event.target.value); updateAction.reset(); }}
            disabled={updateAction.isPending}
            maxLength={120}
            required
          />
          <label htmlFor="edit-notebook-description">Description</label>
          <textarea
            id="edit-notebook-description"
            value={editDescription}
            onChange={(event) => { setEditDescription(event.target.value); updateAction.reset(); }}
            disabled={updateAction.isPending}
            maxLength={1000}
            rows={4}
          />
          {updateAction.error ? <Notice tone="error">{getErrorMessage(updateAction.error)}</Notice> : null}
        </form>
      </Dialog>

      <ConfirmationDialog
        open={Boolean(deleteNotebook)}
        onClose={() => {
          if (!deleteAction.isPending) setDeleteNotebook(null);
        }}
        onConfirm={() => void handleDelete()}
        title="Delete empty notebook?"
        description={
          <>
            <strong>{deleteNotebook?.name}</strong> will be removed. Documents are never deleted through this action.
            {deleteAction.error ? <Notice tone="error">{getErrorMessage(deleteAction.error)}</Notice> : null}
          </>
        }
        confirmLabel="Delete notebook"
        destructive
        loading={deleteAction.isPending}
      />
    </div>
  );
}

export default NotebooksPage;
