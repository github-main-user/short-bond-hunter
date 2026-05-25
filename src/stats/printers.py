import pandas as pd


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
            f"spent: {r['spent_bond']:.2f}₽,"
            f" return: {r['return_per_bond'] * r['qty']:.2f}₽,"
            f" total returned: {r['returned_bond']:.2f}₽,"
            f" annual yield: {r['bond_yield']:.2f}%"
            ")"
            "\nTMON:"
            " ("
            f"spent: {r['spent_tmon']:.2f}₽,"
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


def print_per_month(df: pd.DataFrame) -> None:
    if df.empty:
        print("no data to display")
        return

    for month, r in df.iterrows():
        print(
            f"\n{month}:"
            f"\nBOND: spent {r['spent_bond']:.2f}₽,"
            f" return {r['returned_bond']:.2f}₽"
            f" (annual yield {r['bond_yield']:.2f}%)"
            f"\nTMON: spent {r['spent_tmon']:.2f}₽,"
            f" return {r['returned_tmon']:.2f}₽"
            f" (annual yield {r['tmon_yield']:.2f}%)"
        )

    total_spent_bond = df["spent_bond"].sum()
    total_spent_tmon = df["spent_tmon"].sum()
    total_ret_bond = df["returned_bond"].sum()
    total_ret_tmon = df["returned_tmon"].sum()
    print(
        "\n"
        + "=" * 50
        + (
            f"\nTotal spent BOND: {total_spent_bond:.2f}₽,"
            f" returned: {total_ret_bond:.2f}₽"
            f"\nTotal spent TMON: {total_spent_tmon:.2f}₽,"
            f" returned: {total_ret_tmon:.2f}₽"
        )
    )


def print_per_bond(df: pd.DataFrame) -> None:
    if df.empty:
        print("no data to display")
        return

    for (ticker, name), r in df.iterrows():
        print(
            f'\n"{name}" ({ticker}):'
            f" {r['purchases']} purchase(s), {r['total_qty']} bonds total"
            f" | {r['first_bought']} -> {r['last_received']}"
            f" (avg {r['avg_days']:.0f} days)"
            f"\nBOND: spent {r['total_spent']:.2f}₽,"
            f" returned {r['total_returned']:.2f}₽,"
            f" annual yield {r['bond_yield']:.2f}%"
            f"\nTMON: spent {r['total_spent_tmon']:.2f}₽,"
            f" returned {r['total_returned_tmon']:.2f}₽,"
            f" annual yield {r['tmon_yield']:.2f}%"
            f"\nbond vs tmon delta: {r['bond_vs_tmon_delta']:+.2f}₽"
        )

    total_ret = df["total_returned"].sum()
    total_ret_tmon = df["total_returned_tmon"].sum()
    print(
        "\n"
        + "=" * 50
        + (
            f"\nTotal returned BOND: {total_ret:.2f}₽"
            f"\nTotal returned TMON: {total_ret_tmon:.2f}₽"
            f"\nTotal bond vs tmon delta: {total_ret - total_ret_tmon:+.2f}₽"
        )
    )
