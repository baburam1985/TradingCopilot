import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";

export default function PriceChart({ bars, trades }) {
  const data = bars.map(b => ({
    time: new Date(b.timestamp).toLocaleTimeString(),
    price: parseFloat(b.close),
  }));

  const buyTimes = new Set(trades.filter(t => t.action === "buy").map(t =>
    new Date(t.timestamp_open).toLocaleTimeString()
  ));
  const sellTimes = new Set(trades.filter(t => t.action === "sell").map(t =>
    new Date(t.timestamp_open).toLocaleTimeString()
  ));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="time" tick={{ fontSize: 10 }} />
        <YAxis domain={["auto", "auto"]} />
        <Tooltip />
        <Line type="monotone" dataKey="price" dot={false} stroke="#2563eb" strokeWidth={2} />
        {data.map((d, i) =>
          buyTimes.has(d.time) ? <ReferenceLine key={`b${i}`} x={d.time} stroke="green" label="B" /> : null
        )}
        {data.map((d, i) =>
          sellTimes.has(d.time) ? <ReferenceLine key={`s${i}`} x={d.time} stroke="red" label="S" /> : null
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
