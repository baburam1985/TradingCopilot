import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "./components/AppShell";
import NewSession from "./pages/NewSession";
import LiveDashboard from "./pages/LiveDashboard";
import Reports from "./pages/Reports";
import Optimize from "./pages/Optimize";
import AlertPreferences from "./pages/AlertPreferences";
import { NotificationProvider } from "./context/NotificationContext";

export default function App() {
  return (
    <NotificationProvider>
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<NewSession />} />
          <Route path="/dashboard/:sessionId" element={<LiveDashboard />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/optimize" element={<Optimize />} />
          <Route path="/alerts" element={<AlertPreferences />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
    </NotificationProvider>
  );
}
