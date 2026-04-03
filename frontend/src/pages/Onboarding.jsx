import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getStrategies, createSession, getSparkline } from "../api/client";

const PRESET_SYMBOLS = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ"];

function Sparkline({ data }) {
  if (!data || data.length < 2) {
    return <div className="w-16 h-6 opacity-30 text-[#555] text-[10px] flex items-center">no data</div>;
  }
  const closes = data.map((d) => d.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const w = 64;
  const h = 24;
  const pts = closes.map((c, i) => {
    const x = (i / (closes.length - 1)) * w;
    const y = h - ((c - min) / range) * h;
    return `${x},${y}`;
  });
  const isUp = closes[closes.length - 1] >= closes[0];
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke={isUp ? "#00e676" : "#ef5350"}
        strokeWidth="1.5"
      />
    </svg>
  );
}

function StepDots({ current, total }) {
  return (
    <div className="flex gap-2 justify-center mb-6">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`w-2 h-2 rounded-full transition-colors ${
            i === current ? "bg-[#00e676]" : "bg-[#333]"
          }`}
        />
      ))}
    </div>
  );
}

export default function Onboarding({ onDismiss }) {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [capital, setCapital] = useState(100);
  const [symbol, setSymbol] = useState("");
  const [symbolInput, setSymbolInput] = useState("");
  const [sparklines, setSparklines] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getStrategies().then((r) => {
      const list = r.data;
      setStrategies(list);
      if (list.length > 0) setSelectedStrategy(list[0].name);
    });
  }, []);

  useEffect(() => {
    if (step === 2) {
      PRESET_SYMBOLS.forEach((sym) => {
        getSparkline(sym)
          .then((r) => setSparklines((prev) => ({ ...prev, [sym]: r.data })))
          .catch(() => setSparklines((prev) => ({ ...prev, [sym]: [] })));
      });
    }
  }, [step]);

  const dismiss = () => {
    localStorage.setItem("onboarded", "true");
    onDismiss();
  };

  const handleComplete = async () => {
    const finalSymbol = (symbolInput.trim() || symbol).toUpperCase();
    if (!finalSymbol) {
      setError("Please pick or enter a symbol.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await createSession({
        symbol: finalSymbol,
        strategy: selectedStrategy,
        strategy_params: {},
        starting_capital: capital,
        mode: "paper",
      });
      localStorage.setItem("onboarded", "true");
      navigate(`/dashboard/${resp.data.id}`);
    } catch (err) {
      setError(err?.response?.data?.detail ?? "Failed to create session.");
      setLoading(false);
    }
  };

  const selectedStrategyObj = strategies.find((s) => s.name === selectedStrategy);

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 px-4">
      <div className="bg-[#141414] border border-[#1e1e1e] rounded-xl w-full max-w-lg p-6 md:p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-[#00e676] text-xs uppercase tracking-widest font-semibold">
            Welcome to Trading Copilot
          </span>
          <button
            onClick={dismiss}
            className="text-[#555] hover:text-[#888] text-xs underline"
          >
            Skip
          </button>
        </div>

        <StepDots current={step} total={3} />

        {/* Step 1 — Strategy */}
        {step === 0 && (
          <div>
            <h2 className="text-white text-lg font-semibold mb-1">Pick a Strategy</h2>
            <p className="text-[#888] text-xs mb-4">
              Choose the trading methodology your session will follow.
            </p>
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {strategies.map((s) => (
                <button
                  key={s.name}
                  onClick={() => setSelectedStrategy(s.name)}
                  className={`w-full text-left rounded-lg border px-4 py-3 transition-colors ${
                    selectedStrategy === s.name
                      ? "border-[#00e676] bg-[#00e676]/5"
                      : "border-[#1e1e1e] hover:border-[#333]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-white text-sm font-medium capitalize">
                      {s.name.replace(/_/g, " ")}
                    </span>
                    {s.avg_win_rate != null && (
                      <span className="text-[#00e676] text-xs">
                        {(s.avg_win_rate * 100).toFixed(0)}% win rate
                      </span>
                    )}
                  </div>
                  <p className="text-[#666] text-xs mt-0.5 leading-snug">{s.description}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2 — Capital */}
        {step === 1 && (
          <div>
            <h2 className="text-white text-lg font-semibold mb-1">Set Your Capital</h2>
            <p className="text-[#888] text-xs mb-6">
              This is simulated money — nothing real is moved.
            </p>
            <div className="text-center mb-4">
              <span className="text-[#00e676] text-4xl font-bold">${capital.toLocaleString()}</span>
            </div>
            <input
              type="range"
              min={10}
              max={10000}
              step={10}
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="w-full accent-[#00e676]"
            />
            <div className="flex justify-between text-[#555] text-xs mt-1">
              <span>$10</span>
              <span>$10,000</span>
            </div>
            <div className="mt-4 flex gap-2 flex-wrap">
              {[100, 500, 1000, 5000].map((v) => (
                <button
                  key={v}
                  onClick={() => setCapital(v)}
                  className={`px-3 py-1 rounded text-xs border transition-colors ${
                    capital === v
                      ? "border-[#00e676] text-[#00e676] bg-[#00e676]/5"
                      : "border-[#1e1e1e] text-[#888] hover:border-[#333]"
                  }`}
                >
                  ${v.toLocaleString()}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 3 — Symbol */}
        {step === 2 && (
          <div>
            <h2 className="text-white text-lg font-semibold mb-1">Pick a Symbol</h2>
            <p className="text-[#888] text-xs mb-4">
              Choose a preset or type any ticker symbol.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
              {PRESET_SYMBOLS.map((sym) => (
                <button
                  key={sym}
                  onClick={() => {
                    setSymbol(sym);
                    setSymbolInput("");
                  }}
                  className={`rounded-lg border px-3 py-2 flex items-center justify-between transition-colors ${
                    symbol === sym && !symbolInput
                      ? "border-[#00e676] bg-[#00e676]/5"
                      : "border-[#1e1e1e] hover:border-[#333]"
                  }`}
                >
                  <span className="text-white text-sm font-medium">{sym}</span>
                  <Sparkline data={sparklines[sym]} />
                </button>
              ))}
            </div>
            <input
              type="text"
              className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] uppercase placeholder-[#444]"
              placeholder="Or type a symbol (e.g. MSFT)"
              value={symbolInput}
              onChange={(e) => {
                setSymbolInput(e.target.value.toUpperCase());
                setSymbol("");
              }}
              maxLength={10}
            />
            {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
          </div>
        )}

        {/* Footer buttons */}
        <div className="mt-6 flex gap-3">
          {step > 0 && (
            <button
              onClick={() => setStep((s) => s - 1)}
              className="flex-1 py-2.5 rounded-lg border border-[#1e1e1e] text-[#888] text-sm hover:border-[#333] transition-colors"
            >
              Back
            </button>
          )}
          {step < 2 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={step === 0 && !selectedStrategy}
              className="flex-1 py-2.5 rounded-lg bg-[#00e676] text-black text-sm font-semibold hover:bg-[#00c853] transition-colors disabled:opacity-40"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleComplete}
              disabled={loading || (!symbol && !symbolInput.trim())}
              className="flex-1 py-2.5 rounded-lg bg-[#00e676] text-black text-sm font-semibold hover:bg-[#00c853] transition-colors disabled:opacity-40"
            >
              {loading ? "Starting…" : "Start Trading"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
