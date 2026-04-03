import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export const getSessions = () => api.get("/sessions");
export const createSession = (data) => api.post("/sessions", data);
export const stopSession = (id) => api.patch(`/sessions/${id}/stop`);
export const getStrategies = () => api.get("/strategies");
export const getTrades = (sessionId) => api.get(`/sessions/${sessionId}/trades`);
export const getPnl = (sessionId) => api.get(`/sessions/${sessionId}/pnl`);
export const getEquityCurve = (sessionId) => api.get(`/sessions/${sessionId}/equity-curve`);
export const runBacktest = (data) => api.post("/backtest", data);
export const runBacktestCompare = (data) => api.post("/backtest/compare", data);
export const runOptimize = (data) => api.post("/backtest/optimize", data);
export const getLatestPrice = (symbol) => api.get(`/symbols/${symbol}/latest`);

export const getAlerts = (sessionId, limit = 20) =>
  api.get("/alerts", { params: { session_id: sessionId, limit } });
export const markAlertRead = (eventId) => api.patch(`/alerts/${eventId}/read`);
export const markAllAlertsRead = (sessionId) =>
  api.post("/alerts/mark-all-read", null, { params: { session_id: sessionId } });
export const updateSession = (id, data) => api.patch(`/sessions/${id}`, data);

export function createSessionSocket(sessionId, onMessage) {
  const ws = new WebSocket(`ws://${window.location.host}/ws/sessions/${sessionId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}
