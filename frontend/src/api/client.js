import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export const getSessions = (filters = {}) => api.get("/sessions", { params: filters });
export const getSession = (sessionId) => api.get(`/sessions/${sessionId}`);
export const getSessionSummary = (sessionId) => api.get(`/sessions/${sessionId}/summary`);
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
export const getSparkline = (symbol) => api.get(`/symbols/${symbol}/sparkline`);

export const getAlerts = (sessionId, limit = 20) =>
  api.get("/alerts", { params: { session_id: sessionId, limit } });
export const markAlertRead = (eventId) => api.patch(`/alerts/${eventId}/read`);
export const markAllAlertsRead = (sessionId) =>
  api.post("/alerts/mark-all-read", null, { params: { session_id: sessionId } });
export const updateSession = (id, data) => api.patch(`/sessions/${id}`, data);
export const getIndicators = (sessionId) => api.get(`/sessions/${sessionId}/indicators`);
export const getChartData = (sessionId) => api.get(`/sessions/${sessionId}/chart-data`);

export const getNotes = (tradeId) => api.get(`/trades/${tradeId}/notes`);
export const createNote = (tradeId, body, tags) => api.post(`/trades/${tradeId}/notes`, { body, tags });
export const deleteNote = (tradeId, noteId) => api.delete(`/trades/${tradeId}/notes/${noteId}`);
export const exportJournal = (sessionId) =>
  api.get(`/sessions/${sessionId}/journal?format=csv`, { responseType: "blob" });

export const getSchedules = () => api.get("/sessions/schedules");
export const createSchedule = (data) => api.post("/sessions/schedules", data);
export const getSchedule = (id) => api.get(`/sessions/schedules/${id}`);
export const updateSchedule = (id, data) => api.patch(`/sessions/schedules/${id}`, data);
export const deleteSchedule = (id) => api.delete(`/sessions/schedules/${id}`);

export function createSessionSocket(sessionId, onMessage) {
  const ws = new WebSocket(`ws://${window.location.host}/ws/sessions/${sessionId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}

// ---------------------------------------------------------------------------
// Watchlist API
// ---------------------------------------------------------------------------

export const getWatchlist = () => api.get("/watchlist");

export const createWatchlistItem = (data) => api.post("/watchlist", data);

export const updateWatchlistItem = (id, data) => api.patch(`/watchlist/${id}`, data);

export const deleteWatchlistItem = (id) => api.delete(`/watchlist/${id}`);

// ---------------------------------------------------------------------------
// Watchlist WebSocket
// ---------------------------------------------------------------------------

export function createWatchlistSocket(onMessage) {
  const ws = new WebSocket(`ws://${window.location.host}/ws/watchlist`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}
