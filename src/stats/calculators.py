import pandas as pd

from .models import BondMaturity, BondPurchase


def per_purchase(
    purchases: list[BondPurchase],
    maturities: list[BondMaturity],
) -> pd.DataFrame:
    figi_to_maturity = {m.bond_figi: m for m in maturities}

    rows = []
    for p in purchases:
        m = figi_to_maturity.get(p.bond_figi)
        if m is None or m.principal_received is None:
            continue
        if (
            p.tmon_price_at_buy is None
            or m.tmon_price_at_maturity is None
            or m.tmon_price_at_money_received is None
        ):
            continue

        rows.append(
            {
                "ticker": p.bond_ticker,
                "name": p.bond_name,
                "qty": p.quantity,
                "real_price": p.real_price,
                "tmon_buy": p.tmon_price_at_buy,
                "tmon_received": m.tmon_price_at_money_received,
                "bought_at": p.bought_at.date(),
                "received_at": m.money_received_at.date(),
                "return_per_bond": m.money_received
                / (m.principal_received / p.nominal),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["days"] = (
        pd.to_datetime(df["received_at"]) - pd.to_datetime(df["bought_at"])
    ).dt.days
    df["qty_tmon"] = df["real_price"] * df["qty"] // df["tmon_buy"]
    df["spent_bond"] = df["real_price"] * df["qty"]
    df["spent_tmon"] = df["tmon_buy"] * df["qty_tmon"]
    df["returned_bond"] = (df["return_per_bond"] - df["real_price"]) * df["qty"]
    df["returned_tmon"] = (df["tmon_received"] - df["tmon_buy"]) * df["qty_tmon"]
    df["bond_yield"] = (
        (df["return_per_bond"] - df["real_price"])
        / df["real_price"]
        * (365.25 / df["days"])
        * 100
    ).where((df["days"] > 0) & (df["real_price"] > 0), 0.0)
    df["tmon_yield"] = (
        (df["tmon_received"] - df["tmon_buy"])
        / df["tmon_buy"]
        * (365.25 / df["days"])
        * 100
    ).where((df["days"] > 0) & (df["tmon_buy"] > 0), 0.0)

    return df


def _weighted_yield(
    df: pd.DataFrame, returned_col: str, spent_col: str, days_w_col: str
) -> tuple[pd.Series, pd.Series]:
    avg_days = (df[days_w_col] / df[spent_col]).where(df[spent_col] > 0, 0.0)
    yield_ = (df[returned_col] / df[spent_col] * (365.25 / avg_days) * 100).where(
        (df[spent_col] > 0) & (avg_days > 0), 0.0
    )
    return yield_


def per_month(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    enriched = df.assign(
        month=pd.to_datetime(df["received_at"]).dt.to_period("M"),
        bond_days_w=df["days"] * df["spent_bond"],
        tmon_days_w=df["days"] * df["spent_tmon"],
    )
    monthly = enriched.groupby("month", as_index=True)[
        [
            "spent_bond",
            "spent_tmon",
            "returned_bond",
            "returned_tmon",
            "bond_days_w",
            "tmon_days_w",
        ]
    ].sum()
    monthly = monthly.asfreq("M", fill_value=0)

    monthly["bond_yield"] = _weighted_yield(
        monthly, "returned_bond", "spent_bond", "bond_days_w"
    )
    monthly["tmon_yield"] = _weighted_yield(
        monthly, "returned_tmon", "spent_tmon", "tmon_days_w"
    )
    monthly = monthly.drop(columns=["bond_days_w", "tmon_days_w"])
    monthly.index = monthly.index.astype(str)
    return monthly


def per_bond(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    enriched = df.assign(
        bond_days_w=df["days"] * df["spent_bond"],
        tmon_days_w=df["days"] * df["spent_tmon"],
    )
    grouped = enriched.groupby(["ticker", "name"], as_index=True).agg(
        purchases=("qty", "count"),
        total_qty=("qty", "sum"),
        total_spent=("spent_bond", "sum"),
        total_returned=("returned_bond", "sum"),
        total_spent_tmon=("spent_tmon", "sum"),
        total_returned_tmon=("returned_tmon", "sum"),
        bond_days_w=("bond_days_w", "sum"),
        tmon_days_w=("tmon_days_w", "sum"),
        avg_days=("days", "mean"),
        first_bought=("bought_at", "min"),
        last_received=("received_at", "max"),
    )
    grouped["bond_vs_tmon_delta"] = (
        grouped["total_returned"] - grouped["total_returned_tmon"]
    )
    grouped["bond_yield"] = _weighted_yield(
        grouped, "total_returned", "total_spent", "bond_days_w"
    )
    grouped["tmon_yield"] = _weighted_yield(
        grouped, "total_returned_tmon", "total_spent_tmon", "tmon_days_w"
    )
    grouped = grouped.drop(columns=["bond_days_w", "tmon_days_w"])
    return grouped
