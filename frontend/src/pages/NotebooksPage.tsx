import { useState, type FormEvent } from "react";
import {
  FilePlus2,
  FileText,
  FolderInput,
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
  SectionHeader,
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

function notebookValue(notebookId: PublicId | null) {
  return notebookId == null ? "unsorted" : String(notebookId);
}

function parseNotebookValue(value: string) {
  return value === "unsorted" ? null : value;
}

export function NotebooksPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [editNotebook, setEditNotebook] = useState<Notebook | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [deleteNotebook, setDeleteNotebook] = useState<Notebook | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [uploadNotebookId, setUploadNotebookId] = useState<string>("unsorted");
  const [assignmentDrafts, setAssignmentDrafts] = useState<
    Record<PublicId, string>
  >({});

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
    (payload: NotebookCreate, signal: AbortSignal) =>
    api.createNotebook(payload, { signal }),
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
      notebooks.reload();
      notebookOptions.reload();
    } catch {
      // Dialog and controlled values remain available for correction.
    }
  }

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editNotebook?.id || !editName.trim()) return;
    try {
      const updated = await updateAction.run({
        id: editNotebook.id,
        payload: {
          name: editName.trim(),
          description: editDescription.trim(),
        },
      });
      if (!updated) return;
      setEditNotebook(null);
      notebooks.reload();
      notebookOptions.reload();
    } catch {
      // Keep edit form open with user input intact.
    }
  }

  async function handleDelete() {
    if (!deleteNotebook?.id) return;
    try {
      const deleted = await deleteAction.run(deleteNotebook.id);
      if (!deleted) return;
      setDeleteNotebook(null);
      reloadLibrary();
    } catch {
      // Confirmation stays open and exposes backend reason.
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
      reloadLibrary();
    } catch {
      // Selected file and target notebook remain set for retry.
    }
  }

  async function handleAssignment(document: DocumentRecord) {
    const draft =
      assignmentDrafts[document.id] ?? notebookValue(document.notebook_id);
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
    return <LoadingState message="Loading your Library…" />;
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
  const documentGroups = [
    {
      id: "unsorted",
      name: "Unsorted",
      documents: documentItems.filter((document) => document.notebook_id == null),
    },
    ...assignmentNotebooks.map((notebook) => ({
      id: String(notebook.id),
      name: notebook.name,
      documents: documentItems.filter(
        (document) => document.notebook_id === notebook.id,
      ),
    })),
  ].filter((group) => group.documents.length > 0);

  return (
    <div className="page-stack library-page">
      <PageHeader
        eyebrow="Your material"
        title="Library"
        description="Upload study material first. Notebooks help organize it, but you can use them later."
        actions={
          <div className="button-group">
            <Link className="button button--primary" to="#upload">
              <FilePlus2 size={18} aria-hidden="true" />
              <span>Upload study material</span>
            </Link>
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
        className="search-form library-search"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setSearch(searchInput.trim());
        }}
      >
        <label htmlFor="library-search">Search your Library</label>
        <div className="search-form__controls">
          <input
            id="library-search"
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search material or notebooks"
            maxLength={255}
          />
          <Button
            variant="secondary"
            type="submit"
            icon={<Search size={18} aria-hidden="true" />}
          >
            Search
          </Button>
        </div>
      </form>

      <section className="page-section library-notebooks">
        <SectionHeader
          title="Organize with notebooks"
          description="Notebooks are optional. Unsorted works like any other group."
        />

        {notebooks.isRefreshing ? (
          <LoadingState compact message="Refreshing notebooks…" />
        ) : null}

        <div className="library-grid">
          <Card tone="muted" className="notebook-card">
            <div className="notebook-card__icon" aria-hidden="true">
              <FolderInput />
            </div>
            <div className="notebook-card__body">
              <div className="notebook-card__heading">
                <h3>
                  <Link to="/notebooks/unsorted">
                    Unsorted
                  </Link>
                </h3>
                <Badge tone="neutral">
                  {notebooks.data.unsorted.document_count} source
                  {notebooks.data.unsorted.document_count === 1 ? "" : "s"}
                </Badge>
              </div>
              <p>Material you have not placed in a notebook yet.</p>
            </div>
          </Card>

          {notebookItems.map((notebook) => (
            <Card key={notebook.id} className="notebook-card">
              <div className="notebook-card__icon" aria-hidden="true">
                <NotebookTabs />
              </div>
              <div className="notebook-card__body">
                <div className="notebook-card__heading">
                  <h3>
                    <Link to={`/notebooks/${notebook.id}`}>{notebook.name}</Link>
                  </h3>
                  <Badge tone="primary">
                    {notebook.document_count} document
                    {notebook.document_count === 1 ? "" : "s"}
                  </Badge>
                </div>
                <p>{notebook.description || "No description added."}</p>
                <div className="button-group notebook-card__actions">
                  <Button
                    variant="ghost"
                    icon={<Pencil size={17} aria-hidden="true" />}
                    onClick={() => {
                      updateAction.reset();
                      setEditNotebook(notebook);
                      setEditName(notebook.name);
                      setEditDescription(notebook.description);
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    icon={<Trash2 size={17} aria-hidden="true" />}
                    disabled={notebook.document_count > 0}
                    title={
                      notebook.document_count > 0
                        ? "Move or remove every document before deleting"
                        : undefined
                    }
                    onClick={() => {
                      deleteAction.reset();
                      setDeleteNotebook(notebook);
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {notebookItems.length === 0 && search ? (
          <EmptyState
            title="No matching notebooks"
            description={`No notebook matched “${search}”. Clear the search or create a new notebook.`}
            action={
              <Button
                variant="secondary"
                onClick={() => {
                  setSearch("");
                  setSearchInput("");
                }}
              >
                Clear search
              </Button>
            }
          />
        ) : null}
      </section>

      <section id="upload" className="page-section">
        <SectionHeader
          title="Upload study material"
          description="Add a PDF, text file, or presentation. You can organize it now or later."
        />
        <Card>
          <form className="form-grid" onSubmit={handleUpload}>
            <div className="field-stack form-grid__wide">
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
              <p className="field-help">
                Files that are protected, empty, damaged, unsupported, or too
                large cannot be added.
              </p>
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
                  <option key={notebook.id} value={notebook.id ?? ""}>
                    {notebook.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-actions">
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
          </form>
          {uploadAction.error ? (
            <Notice tone="error" title="Upload failed">
              {getErrorMessage(uploadAction.error)} Choose another file or retry.
            </Notice>
          ) : null}
          {uploadAction.data ? (
            <Notice
              tone={uploadAction.data.duplicate ? "warning" : "success"}
              title={
                uploadAction.data.duplicate
                  ? "Material already exists"
                  : "Material is ready"
              }
            >
              <div className="upload-success">
                <p>
                  {uploadAction.data.document.filename}
                  {uploadAction.data.duplicate
                    ? " is already in your Library."
                    : " is ready to study."}
                </p>
                <div className="button-group">
                  <Link className="button button--secondary" to="/chat">
                    Ask about this
                  </Link>
                  <Link
                    className="button button--primary"
                    to={`/study-actions?view=quiz&document_ids=${
                      uploadAction.data.document.id
                    }&scope_name=${encodeURIComponent(
                      uploadAction.data.document.filename,
                    )}`}
                  >
                    Practice this
                  </Link>
                </div>
              </div>
            </Notice>
          ) : null}
        </Card>
      </section>

      <section className="page-section library-material">
        <SectionHeader
          title="Study material"
          description="Choose a source to ask a question, practise, or manage its organization."
        />

        {documents.isLoading && !documents.data ? (
          <LoadingState message="Loading study material..." />
        ) : documents.error && !documents.data ? (
          <ErrorState
            title="Study material is unavailable"
            message={getErrorMessage(documents.error)}
            onRetry={documents.retry}
          />
        ) : documentGroups.length ? (
          <div className="library-groups">
            {documentGroups.map((group) => (
              <section
                key={group.id}
                className="library-group"
                aria-labelledby={`library-group-${group.id}`}
              >
                <h3 id={`library-group-${group.id}`}>{group.name}</h3>
                <div className="document-list">
                  {group.documents.map((document) => {
                    const actualValue = notebookValue(document.notebook_id);
                    const draftValue =
                      assignmentDrafts[document.id] ?? actualValue;
                    return (
                      <Card key={document.id} padding="small">
                        <div className="document-row library-source-row">
                          <div className="document-row__identity">
                            <FileText size={20} aria-hidden="true" />
                            <div>
                              <h4>
                                <Link to={`/documents/${document.id}`}>
                                  {document.filename}
                                </Link>
                              </h4>
                              <p>Ready to study</p>
                            </div>
                          </div>
                          <div className="library-source-row__actions">
                            <Link
                              className="button button--secondary"
                              to="/chat"
                            >
                              Ask about this
                            </Link>
                            <Link
                              className="button button--primary"
                              to={`/study-actions?view=quiz&document_ids=${
                                document.id
                              }&scope_name=${encodeURIComponent(
                                document.filename,
                              )}`}
                            >
                              Practice this
                            </Link>
                          </div>
                        </div>
                        <details className="library-manage">
                          <summary>Organize material</summary>
                          <div className="document-row__assignment">
                            <label htmlFor={`assignment-${document.id}`}>
                              Notebook
                            </label>
                            <select
                              id={`assignment-${document.id}`}
                              value={draftValue}
                              disabled={assignAction.isPending}
                              onChange={(event) =>
                                setAssignmentDrafts((current) => ({
                                  ...current,
                                  [document.id]: event.target.value,
                                }))
                              }
                            >
                              <option value="unsorted">Unsorted</option>
                              {assignmentNotebooks.map((notebook) => (
                                <option
                                  key={notebook.id}
                                  value={notebook.id ?? ""}
                                >
                                  {notebook.name}
                                </option>
                              ))}
                            </select>
                            <Button
                              variant="secondary"
                              icon={<FolderInput size={17} aria-hidden="true" />}
                              disabled={
                                draftValue === actualValue ||
                                assignAction.isPending
                              }
                              onClick={() => void handleAssignment(document)}
                            >
                              Save
                            </Button>
                          </div>
                        </details>
                      </Card>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <EmptyState
            title={search ? "No matching material" : "Your Library is empty"}
            description={
              search
                ? `No material matched "${search}".`
                : "Upload study material first. Notebooks are optional and can be used later."
            }
            icon={<FileText />}
          />
        )}

        {assignAction.error ? (
          <Notice tone="error" title="Assignment was not saved">
            {getErrorMessage(assignAction.error)} Your selected destination is preserved.
          </Notice>
        ) : null}
      </section>

      <Dialog
        open={createOpen}
        onClose={() => {
          if (!createAction.isPending) setCreateOpen(false);
        }}
        title="Create notebook"
        description="Add a focused home for related study material."
        actions={
          <>
            <Button
              variant="ghost"
              onClick={() => setCreateOpen(false)}
              disabled={createAction.isPending}
            >
              Cancel
            </Button>
            <Button
              form="create-notebook-form"
              type="submit"
              loading={createAction.isPending}
              loadingText="Creating…"
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
            onChange={(event) => {
              setCreateName(event.target.value);
              createAction.reset();
            }}
            disabled={createAction.isPending}
            maxLength={120}
            required
            autoFocus
          />
          <label htmlFor="create-notebook-description">Description</label>
          <textarea
            id="create-notebook-description"
            value={createDescription}
            onChange={(event) => {
              setCreateDescription(event.target.value);
              createAction.reset();
            }}
            disabled={createAction.isPending}
            maxLength={1000}
            rows={4}
          />
          {createAction.error ? (
            <Notice tone="error">{getErrorMessage(createAction.error)}</Notice>
          ) : null}
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
            <Button
              variant="ghost"
              onClick={() => setEditNotebook(null)}
              disabled={updateAction.isPending}
            >
              Cancel
            </Button>
            <Button
              form="edit-notebook-form"
              type="submit"
              loading={updateAction.isPending}
              loadingText="Saving…"
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
            onChange={(event) => {
              setEditName(event.target.value);
              updateAction.reset();
            }}
            disabled={updateAction.isPending}
            maxLength={120}
            required
          />
          <label htmlFor="edit-notebook-description">Description</label>
          <textarea
            id="edit-notebook-description"
            value={editDescription}
            onChange={(event) => {
              setEditDescription(event.target.value);
              updateAction.reset();
            }}
            disabled={updateAction.isPending}
            maxLength={1000}
            rows={4}
          />
          {updateAction.error ? (
            <Notice tone="error">{getErrorMessage(updateAction.error)}</Notice>
          ) : null}
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
            <strong>{deleteNotebook?.name}</strong> will be removed. Documents are
            never deleted through this action.
            {deleteAction.error ? (
              <Notice tone="error">{getErrorMessage(deleteAction.error)}</Notice>
            ) : null}
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
