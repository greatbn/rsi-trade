# RSI Trading Bot (Modular)

A robust, modular automated trading bot for XAUUSD (Gold) based on the RSI + WMA45 + EMA9 strategy.

## Features
- **Modular Architecture**: Separated concerns (Signal, Risk, Execution, Connection).
- **Multi-Timeframe Analysis**:
    - **TF3 (H4)**: Trend Bias.
    - **TF2 (H1)**: Entry Zone.
    - **TF1 (M15)**: Confirmation & Execution.
- **Risk Management**:
    - Position sizing based on Risk %.
    - Daily Loss Limit (Circuit Breaker).
    - Consecutive Loss Limit.
- **Robustness**:
    - Automatic MT5 connection retry.
    - Error handling for order placement.
- **Monitoring**:
    - Logging to file and console.
    - Telegram Alerts (configurable).

## Project Structure
```
rsi-trading-tool/
├── config.yaml         # Centralized configuration
├── main.py             # Main execution loop
├── mt5_client.py       # MT5 connection wrapper
├── indicators.py       # Vectorized indicator calculations
├── signal_engine.py    # Core strategy logic (3-TF)
├── risk_manager.py     # Position sizing & safety checks
├── executor.py         # Order execution logic
├── monitor.py          # Logging & Alerts
├── tests/              # Unit tests
│   ├── test_indicators.py
│   └── test_signal_engine.py
├── rsi_strategy.pine   # TradingView Indicator
├── rsi_backtest.pine   # TradingView Backtest Strategy
└── requirements.txt    # Python dependencies
```

## Requirements
- **OS**: Windows (Required for `MetaTrader5` python package).
- **Software**: MetaTrader 5 Terminal installed and logged in.
- **Python**: 3.8+

## Installation
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: `MetaTrader5` package is not available on macOS/Linux.*

2. Configure the bot:
   Edit `config.yaml` with your MT5 login details and trading preferences.

## Usage
Run the bot:
```bash
python main.py
```

## Testing
Run unit tests to verify logic:
```bash
python -m unittest discover tests
```

## TradingView
- `rsi_strategy.pine`: Use this for visual analysis on TradingView.
- `rsi_backtest.pine`: Use this for backtesting the strategy on TradingView.
