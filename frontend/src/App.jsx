import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "./components/AppShell";
import NewSession from "./pages/NewSession";
import LiveDashboard from "./pages/LiveDashboard";
import Reports from "./pages/Reports";
import Optimize from "./pages/Optimize";
import AlertPreferences from "./pages/AlertPreferences";
import Watchlist from "./pages/Watchlist";
import ScheduledSessions from "./pages/ScheduledSessions";
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
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/schedules" element={<ScheduledSessions />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
    </NotificationProvider>
  );
}
