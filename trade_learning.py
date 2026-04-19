import json
from pathlib import Path

import pandas as pd


INPUT_FILE = "robinhood_option_roundtrips.csv"
OUTPUT_SUMMARY = "trade_learning_summary.csv"
OUTPUT_RULES_JSON = "ai_learned_rules.json"


def safe_win_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return round((series == "WIN").mean() * 100, 2)


def load_roundtrips(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = [
        "underlying",
        "option_type",
        "quantity",
        "entry_price",
        "exit_price",
        "total_pnl_dollars",
        "result",
        "holding_days",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["underlying"] = df["underlying"].astype(str).str.upper()
    df["option_type"] = df["option_type"].astype(str).str.upper()
    df["total_pnl_dollars"] = pd.to_numeric(df["total_pnl_dollars"], errors="coerce").fillna(0)
    df["entry_price"] = pd.to_numeric(df["entry_price"], errors="coerce").fillna(0)
    df["exit_price"] = pd.to_numeric(df["exit_price"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["holding_days"] = pd.to_numeric(df["holding_days"], errors="coerce").fillna(0)

    return df


def build_symbol_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for symbol, g in df.groupby("underlying"):
        trades = len(g)
        wins = int((g["result"] == "WIN").sum())
        losses = int((g["result"] == "LOSS").sum())
        win_rate = safe_win_rate(g["result"])
        total_pnl = round(g["total_pnl_dollars"].sum(), 2)
        avg_pnl = round(g["total_pnl_dollars"].mean(), 2)
        avg_entry = round(g["entry_price"].mean(), 2)
        avg_hold_days = round(g["holding_days"].mean(), 2)

        call_df = g[g["option_type"] == "C"]
        put_df = g[g["option_type"] == "P"]

        call_pnl = round(call_df["total_pnl_dollars"].sum(), 2) if len(call_df) else 0.0
        put_pnl = round(put_df["total_pnl_dollars"].sum(), 2) if len(put_df) else 0.0
        call_win_rate = safe_win_rate(call_df["result"]) if len(call_df) else 0.0
        put_win_rate = safe_win_rate(put_df["result"]) if len(put_df) else 0.0

        rows.append(
            {
                "symbol": symbol,
                "trades": trades,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": win_rate,
                "total_pnl_dollars": total_pnl,
                "avg_pnl_dollars": avg_pnl,
                "avg_entry_price": avg_entry,
                "avg_holding_days": avg_hold_days,
                "call_pnl_dollars": call_pnl,
                "put_pnl_dollars": put_pnl,
                "call_win_rate_pct": call_win_rate,
                "put_win_rate_pct": put_win_rate,
            }
        )

    summary = pd.DataFrame(rows).sort_values(
        ["total_pnl_dollars", "win_rate_pct", "trades"],
        ascending=[False, False, False],
    )
    return summary.reset_index(drop=True)


def build_rules(summary: pd.DataFrame) -> dict:
    min_trades_for_decision = 8

    allowed_symbols = []
    blocked_symbols = []
    review_symbols = []

    for _, row in summary.iterrows():
        symbol = row["symbol"]
        trades = int(row["trades"])
        total_pnl = float(row["total_pnl_dollars"])
        win_rate = float(row["win_rate_pct"])

        if trades < min_trades_for_decision:
            review_symbols.append(symbol)
            continue

        if total_pnl > 0 and win_rate >= 35:
            allowed_symbols.append(symbol)
        elif total_pnl < 0 and win_rate < 35:
            blocked_symbols.append(symbol)
        else:
            review_symbols.append(symbol)

    qqq_row = summary[summary["symbol"] == "QQQ"]
    spy_row = summary[summary["symbol"] == "SPY"]

    learned = {
        "allowed_symbols": allowed_symbols,
        "blocked_symbols": blocked_symbols,
        "review_symbols": review_symbols,
        "edge_mode": "QQQ_FOCUSED",
        "spy_min_score": 8,
        "high_price_warning_threshold": 650,
        "notes": [],
    }

    if not qqq_row.empty:
        learned["notes"].append(
            f"QQQ trades={int(qqq_row.iloc[0]['trades'])}, pnl={float(qqq_row.iloc[0]['total_pnl_dollars'])}"
        )

    if not spy_row.empty:
        spy_pnl = float(spy_row.iloc[0]["total_pnl_dollars"])
        spy_win = float(spy_row.iloc[0]["win_rate_pct"])
        learned["notes"].append(f"SPY trades={int(spy_row.iloc[0]['trades'])}, pnl={spy_pnl}, win_rate={spy_win}")
        if spy_pnl < 0 or spy_win < 35:
            learned["spy_min_score"] = 9

    return learned


def main():
    path = Path(INPUT_FILE)
    if not path.exists():
        raise FileNotFoundError(f"Could not find {INPUT_FILE} in the current folder.")

    df = load_roundtrips(INPUT_FILE)
    summary = build_symbol_summary(df)
    rules = build_rules(summary)

    summary.to_csv(OUTPUT_SUMMARY, index=False)
    with open(OUTPUT_RULES_JSON, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)

    print("\n=== TOP SYMBOLS BY TOTAL PNL ===")
    print(summary[["symbol", "trades", "win_rate_pct", "total_pnl_dollars"]].head(10).to_string(index=False))

    print("\n=== WORST SYMBOLS BY TOTAL PNL ===")
    print(
        summary.sort_values("total_pnl_dollars")[["symbol", "trades", "win_rate_pct", "total_pnl_dollars"]]
        .head(10)
        .to_string(index=False)
    )

    print("\n=== LEARNED RULES ===")
    print(json.dumps(rules, indent=2))

    print(f"\nSaved: {OUTPUT_SUMMARY}")
    print(f"Saved: {OUTPUT_RULES_JSON}")


if __name__ == "__main__":
    main()