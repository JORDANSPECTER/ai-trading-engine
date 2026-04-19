import pandas as pd

df = pd.read_csv("robinhood_option_roundtrips.csv")

# =========================
# BASIC STATS
# =========================
print("\n=== OVERVIEW ===")
print("Total Trades:", len(df))
print("Win Rate:", (df["result"] == "WIN").mean())
print("Total PnL:", df["total_pnl_dollars"].sum())

# =========================
# CALL vs PUT
# =========================
print("\n=== CALL vs PUT ===")
print(df.groupby("option_type")["total_pnl_dollars"].sum())
print(df.groupby("option_type")["result"].value_counts(normalize=True))

# =========================
# SYMBOL PERFORMANCE
# =========================
print("\n=== SYMBOL PERFORMANCE ===")
print(df.groupby("underlying")["total_pnl_dollars"].sum().sort_values(ascending=False).head(10))

# =========================
# HOLD TIME
# =========================
print("\n=== HOLD TIME ===")
print(df.groupby("holding_days")["total_pnl_dollars"].mean())

# =========================
# BIGGEST WINS / LOSSES
# =========================
print("\n=== BEST TRADES ===")
print(df.sort_values("total_pnl_dollars", ascending=False).head(5))

print("\n=== WORST TRADES ===")
print(df.sort_values("total_pnl_dollars").head(5))