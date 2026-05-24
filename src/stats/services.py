import logging
from typing import cast

import matplotlib.pyplot as plt
import pandas as pd

from .models import BondMaturity, BondPurchase
from .repositories import MaturityRepository, PurchaseRepository

logger = logging.getLogger(__name__)


def calculate_per_purchase(
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


def print_per_purchase(df: pd.DataFrame) -> None:
    if df.empty:
        print("no data to display")
        return

    for _, r in df.iterrows():
        print(
            f'\n"{r["name"]}" ({r["ticker"]}) (x{r["qty"]}):'
            f" {r['bought_at']} -> {r['received_at']}"
            f" ({r['days']} days)"
            "\nBOND:"
            " ("
            f"spent: {r['real_price'] * r['qty']:.2f}₽,"
            f" return: {r['return_per_bond'] * r['qty']:.2f}₽,"
            f" total returned: {r['returned_bond']:.2f}₽,"
            f" annual yield: {r['bond_yield']:.2f}%"
            ")"
            "\nTMON:"
            " ("
            f"spent: {r['tmon_buy'] * r['qty_tmon']:.2f}₽,"
            f" return: {r['tmon_received'] * r['qty_tmon']:.2f}₽,"
            f" total returned: {r['returned_tmon']:.2f}₽,"
            f" annual yield: {r['tmon_yield']:.2f}%"
            ")"
        )

    print(
        "\n"
        + "=" * 50
        + (
            f"\nTotal returned BOND: {df['returned_bond'].sum():.2f}₽"
            f"\nTotal returned TMON: {df['returned_tmon'].sum():.2f}₽"
        )
        + "\n"
        + "=" * 50
        + (
            f"\nAverage BOND yield: {df['bond_yield'].mean():.2f}%"
            f"\nAverage TMON yield: {df['tmon_yield'].mean():.2f}%"
        )
    )

    ax = df.plot(
        x="received_at",
        y=["bond_yield", "tmon_yield"],
        kind="bar",
    )
    ax.set_xlabel("received at")
    ax.set_ylabel("annual yield %")
    plt.tight_layout()
    plt.show()


def generate_statistics():
    purchase_repo = cast(PurchaseRepository, PurchaseRepository())
    maturity_repo = cast(MaturityRepository, MaturityRepository())

    df = calculate_per_purchase(purchase_repo.get_all(), maturity_repo.get_all())
    print_per_purchase(df)
