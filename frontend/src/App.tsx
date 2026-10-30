import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import AskPage from "./pages/AskPage";
import CollectionPage from "./pages/CollectionPage";
import CoursePage from "./pages/CoursePage";
import DashboardPage from "./pages/DashboardPage";
import DocPageView from "./pages/DocPageView";
import LearnPage from "./pages/LearnPage";
import LessonPage from "./pages/LessonPage";
import LibraryPage from "./pages/LibraryPage";
import LoginPage from "./pages/LoginPage";
import NewPage from "./pages/NewPage";
import ReviewPage from "./pages/ReviewPage";
import SettingsPage from "./pages/SettingsPage";
import VideoPage from "./pages/VideoPage";

export default function App() {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="center-screen">
        <Spinner />
      </div>
    );
  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<LoginPage />} />
      </Routes>
    );
  }
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/new" element={<NewPage />} />
        <Route path="/learn" element={<LearnPage />} />
        <Route path="/learn/:courseId" element={<CoursePage />} />
        <Route path="/learn/:courseId/lessons/:lessonId" element={<LessonPage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/collections/:id" element={<CollectionPage />} />
        <Route path="/collections/:id/pages/:pageId" element={<DocPageView />} />
        <Route path="/videos/:id" element={<VideoPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
