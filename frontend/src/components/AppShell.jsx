import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { label: "New Session", to: "/" },
  { label: "Dashboard", to: "/dashboard" },
  { label: "Reports", to: "/reports" },
];

export default function AppShell({ children }) {
  const { pathname } = useLocation();

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white">
      {/* Sidebar */}
      <aside className="w-[200px] flex-shrink-0 bg-[#111] flex flex-col fixed top-0 left-0 h-full">
        {/* Brand block */}
        <div className="px-4 pt-6 pb-4 border-b border-[#1e1e1e]">
          <div className="text-[#00e676] font-bold text-sm tracking-widest uppercase">Trading Copilot</div>
          <div className="text-[#555] text-xs mt-1 tracking-wide">PAPER MODE ACTIVE</div>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-4">
          {NAV_ITEMS.map(({ label, to }) => {
            const isActive =
              to === "/"
                ? pathname === "/"
                : pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "text-[#00e676] bg-[#141414] border-l-2 border-[#00e676]"
                    : "text-[#888] hover:text-white hover:bg-[#141414]"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Bottom items */}
        <div className="border-t border-[#1e1e1e] py-4">
          <button className="flex items-center w-full px-4 py-2.5 text-sm text-[#888] hover:text-white hover:bg-[#141414] transition-colors">
            Help
          </button>
          <button className="flex items-center w-full px-4 py-2.5 text-sm text-[#888] hover:text-white hover:bg-[#141414] transition-colors">
            Logout
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 ml-[200px] flex flex-col min-h-screen">
        {/* Top bar */}
        <header className="h-12 bg-[#0d0d0d] border-b border-[#1e1e1e] flex items-center px-6 fixed top-0 left-[200px] right-0 z-10">
          <span className="text-[#00e676] font-semibold text-sm">TradingCopilot</span>
          <nav className="flex gap-6 ml-8">
            {["Markets", "Terminal", "Alerts"].map((item) => (
              <span key={item} className="text-[#888] text-sm hover:text-white cursor-pointer transition-colors">
                {item}
              </span>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-4">
            <span className="bg-[#00e676] text-black text-xs font-bold px-2 py-0.5 rounded">LIVE STATUS</span>
            <span className="text-[#888] text-sm cursor-pointer hover:text-white">🔔</span>
            <span className="text-[#888] text-sm cursor-pointer hover:text-white">⚙</span>
            <div className="w-7 h-7 rounded-full bg-[#1e1e1e] flex items-center justify-center text-xs text-[#888]">U</div>
          </div>
        </header>

        {/* Scrollable content */}
        <main className="flex-1 mt-12 bg-[#0d0d0d] overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
