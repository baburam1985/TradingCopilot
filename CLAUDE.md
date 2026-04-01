# TradingCopilot

## Project Overview

TradingCopilot is a day trading application that analyzes market signals for any stock symbol and executes (or simulates) trades using time-tested strategies from historical trading gurus.

The end goal: make money for the user by faithfully following the methodology they select.

---

## Core Features

### 1. Market Signal Analysis
- Monitors and evaluates market signals for any given stock symbol
- Signals feed into strategy logic to generate buy/sell/hold decisions

### 2. Trading Strategies
- Implements multiple well-known strategies from trading literature (spanning ~100 years of methodology)
- Strategies are selectable by the user at runtime
- Examples: trend following, mean reversion, momentum, breakout, etc.

### 3. User-Configured Trading Sessions
- User provides:
  - A stock symbol to trade
  - A capital amount (e.g., $100)
  - A strategy to apply
- The selected strategy runs autonomously in the background, making trading decisions

---

## Two Operating Modes

### Live Trading Mode
- Connects to a brokerage or exchange API
- Executes real trades with real capital
- Full audit trail of orders and fills

### Paper Trading Mode (Simulation / "Mimic")
- No real money is moved
- User allocates a hypothetical amount (e.g., $100)
- The system tracks exactly what *would have happened* if those trades were executed
- Shows hypothetical P&L, win rate, drawdown, and other performance metrics
- Intended for strategy validation and user confidence-building before going live

---

## Design Principles

- **Strategy-first**: Core trading logic is modular — each strategy is an independent, testable unit
- **Mode-agnostic execution**: The same strategy logic runs in both live and paper modes; only the order execution layer differs
- **Transparency**: Every signal, decision, and (simulated or real) trade is logged and explainable
- **Safety**: Paper trading is the default; live trading requires explicit opt-in

---

## Out of Scope (for now)
- Multi-asset portfolios (single stock per session initially)
- Options, futures, or crypto (equities only initially)
- Social/copy trading features
