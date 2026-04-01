import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import NewSession from "./pages/NewSession";
import LiveDashboard from "./pages/LiveDashboard";
import Reports from "./pages/Reports";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ padding: "1rem", borderBottom: "1px solid #ddd", display: "flex", gap: "1rem" }}>
        <Link to="/">New Session</Link>
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/reports">Reports</Link>
      </nav>
      <Routes>
        <Route path="/" element={<NewSession />} />
        <Route path="/dashboard/:sessionId" element={<LiveDashboard />} />
        <Route path="/reports" element={<Reports />} />
      </Routes>
    </BrowserRouter>
  );
}
