import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import AskPage from "./pages/AskPage";
import CollectionPage from "./pages/CollectionPage";
import LibraryPage from "./pages/LibraryPage";
import LoginPage from "./pages/LoginPage";
import NewPage from "./pages/NewPage";
import SettingsPage from "./pages/SettingsPage";
import VideoPage from "./pages/VideoPage";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-screen"><div className="spinner" /></div>;
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
        <Route path="/" element={<NewPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/collections/:id" element={<CollectionPage />} />
        <Route path="/videos/:id" element={<VideoPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
