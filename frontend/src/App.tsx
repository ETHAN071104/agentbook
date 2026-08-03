import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { AppShell } from "./layouts";
import {
  ChatPage,
  DashboardPage,
  DocumentDetailPage,
  MemoryPage,
  LearningAgentPage,
  NotebookDetailPage,
  NotebooksPage,
  NotFoundPage,
  ProgressPage,
  StudyActionsPage,
  StudyTasksPage,
  SystemPage,
  TopicWorkspacePage,
} from "./pages";

const LandingPage = lazy(() => import("./pages/LandingPage"));

export function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <Suspense
            fallback={
              <main className="guest-gate" aria-live="polite">
                <p>Opening Agentbook...</p>
              </main>
            }
          >
            <LandingPage />
          </Suspense>
        }
      />
      <Route
        element={
          <AppShell />
        }
      >
        <Route path="app" element={<DashboardPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="agent" element={<LearningAgentPage />} />
        <Route path="notebooks" element={<NotebooksPage />} />
        <Route path="notebooks/:notebookId" element={<NotebookDetailPage />} />
        <Route path="documents/:documentId" element={<DocumentDetailPage />} />
        <Route path="topics/:topicId" element={<TopicWorkspacePage />} />
        <Route path="study-actions" element={<StudyActionsPage />} />
        <Route path="tasks" element={<StudyTasksPage />} />
        <Route path="progress" element={<ProgressPage />} />
        <Route path="memory" element={<MemoryPage />} />
        <Route path="system" element={<SystemPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default App;
