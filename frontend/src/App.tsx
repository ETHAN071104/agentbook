import { Route, Routes } from "react-router-dom";
import { GraduationCap } from "lucide-react";

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

export function App() {
  return (
    <Routes>
      <Route
        element={
          <AppShell
            footer={
              <div className="app-sidebar__profile">
                <span className="app-sidebar__avatar" aria-hidden="true">
                  <GraduationCap size={19} />
                </span>
                <span className="app-sidebar__profile-copy">
                  <strong>Private study space</strong>
                  <span>Saved in this browser</span>
                </span>
              </div>
            }
          />
        }
      >
        <Route index element={<DashboardPage />} />
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
