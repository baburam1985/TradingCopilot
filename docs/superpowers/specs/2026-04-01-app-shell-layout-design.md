# App Shell Layout Design

**Date:** 2026-04-01  
**Status:** Approved

## Goal

Redesign the TradingCopilot frontend with a consistent dark-theme layout across all three pages (New Session, Live Dashboard, Reports), using an App Shell component pattern and Tailwind CSS.

## Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Branding | TradingCopilot (existing name) | Keep product identity |
| CSS | Tailwind CSS | Best fit for dark theme, fast to build, replaces inline styles |
| Layout pattern | App Shell component | Zero duplication; sidebar and top bar defined once |
| State management | No change (React hooks) | No new complexity needed for 3 pages |

## Layout Structure

```
AppShell
├── Sidebar (fixed left, 200px wide)
│   ├── Brand block: "TRADING COPILOT" + "PAPER MODE ACTIVE"
│   ├── Nav items: New Session, Dashboard, Reports (with icons, active highlight)
│   └── Bottom items: Help, Logout
├── Main (flex-1)
│   ├── TopBar (fixed height ~48px)
│   │   ├── Left: "TradingCopilot" brand text (green)
│   │   ├── Centre: Markets · Terminal · Alerts nav links
│   │   └── Right: LIVE STATUS badge · bell · settings · avatar
│   └── Content (scrollable)
│       └── <Outlet /> — page renders here
```

## Page Anatomy (each page)

Every page follows the same internal structure:

1. **Page header** — breadcrumb (e.g. HOME › NEW SESSION), page title, subtitle
2. **Metrics row** — 3–4 stat cards (label + value, green accent for positive figures)
3. **Page body** — page-specific content (form, charts, table, etc.)

### New Session
- Metrics: Expected Volatility · Market Liquidity · Backtest Win-Rate
- Body: left panel (Asset Selection, Algorithm Parameters, Execution Logic form) + right panel (session preview / awaiting state)

### Live Dashboard
- Metrics: Current Price · Open P&L · Total Trades · Win Rate
- Body: Price chart (Recharts) + P&L bar chart, Trade Log table below

### Reports
- Metrics: Total Sessions · Total P&L · Avg Win Rate
- Body: Session History list (symbol badge · name · date · P&L + ROI)

## Colour Tokens (Tailwind classes)

| Token | Value | Usage |
|-------|-------|-------|
| `bg-[#0a0a0a]` | near-black | Body / page background |
| `bg-[#0d0d0d]` | dark | Top bar, content area |
| `bg-[#111]` | sidebar | Sidebar background |
| `bg-[#141414]` | card | Metric cards, panels |
| `border-[#1e1e1e]` | subtle | All borders |
| `text-[#00e676]` | green | Brand, active nav, positive values, section labels, CTA button |
| `text-white` | white | Page titles, primary values |
| `text-[#888]` | mid-grey | Inactive nav items, secondary labels |
| `text-[#555]` | dim-grey | Subtitles, metadata |
| `text-[#ff4444]` | red | Negative P&L values |

## Components to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/components/AppShell.jsx` | Create | Sidebar + TopBar wrapper |
| `frontend/src/App.jsx` | Modify | Wrap routes in AppShell, install Tailwind |
| `frontend/src/pages/NewSession.jsx` | Modify | Remove inline styles, use Tailwind, adopt page anatomy |
| `frontend/src/pages/LiveDashboard.jsx` | Modify | Remove inline styles, use Tailwind, adopt page anatomy |
| `frontend/src/pages/Reports.jsx` | Modify | Remove inline styles, use Tailwind, adopt page anatomy |
| `frontend/src/components/MetricCard.jsx` | Create | Reusable stat card (label + value + optional colour) |
| `frontend/src/components/PageHeader.jsx` | Create | Reusable breadcrumb + title + subtitle block |
| `frontend/tailwind.config.js` | Create | Tailwind config with content paths |
| `frontend/index.css` | Modify | Add Tailwind base/components/utilities directives |

## Tailwind Setup

Install via npm:
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

`tailwind.config.js` content paths:
```js
content: ["./index.html", "./src/**/*.{js,jsx}"]
```

`index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

## Routing

No route changes. `AppShell` wraps `<Routes>` using React Router v6's `<Outlet>`:

```jsx
// App.jsx
<BrowserRouter>
  <AppShell>
    <Routes>
      <Route path="/" element={<NewSession />} />
      <Route path="/dashboard/:sessionId" element={<LiveDashboard />} />
      <Route path="/reports" element={<Reports />} />
    </Routes>
  </AppShell>
</BrowserRouter>
```

## Out of Scope

- No new pages or routes
- No changes to backend API
- No changes to existing Recharts chart logic (just restyled container)
- No authentication or role-based nav visibility
- No responsive/mobile layout (desktop only)
