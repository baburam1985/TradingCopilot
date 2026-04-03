import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "./components/AppShell";
import NewSession from "./pages/NewSession";
import LiveDashboard from "./pages/LiveDashboard";
import Reports from "./pages/Reports";
import Optimize from "./pages/Optimize";

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<NewSession />} />
          <Route path="/dashboard/:sessionId" element={<LiveDashboard />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/optimize" element={<Optimize />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
