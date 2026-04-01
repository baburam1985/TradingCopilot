from strategies.base import StrategyBase, Signal

class BacktestRunner:
    def __init__(self, strategy: StrategyBase, starting_capital: float):
        self.strategy = strategy
        self.starting_capital = starting_capital

    def run(self, bars: list) -> list[dict]:
        trades = []
        open_trade = None

        for i, bar in enumerate(bars):
            # No lookahead: only feed prices up to and including current bar
            closes = [float(b.close) for b in bars[:i + 1]]
            signal = self.strategy.analyze(closes)

            if signal.action == "buy" and open_trade is None:
                quantity = self.starting_capital / float(bar.close)
                open_trade = {
                    "action": "buy",
                    "signal_reason": signal.reason,
                    "price_at_signal": float(bar.close),
                    "quantity": quantity,
                    "timestamp_open": bar.timestamp,
                    "timestamp_close": None,
                    "price_at_close": None,
                    "pnl": None,
                    "status": "open",
                }
                trades.append(open_trade)

            elif signal.action == "sell" and open_trade is not None:
                open_trade["timestamp_close"] = bar.timestamp
                open_trade["price_at_close"] = float(bar.close)
                open_trade["pnl"] = (float(bar.close) - open_trade["price_at_signal"]) * open_trade["quantity"]
                open_trade["status"] = "closed"
                open_trade = None

        return trades
