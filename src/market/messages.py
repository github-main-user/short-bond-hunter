from src.market.domain import EnrichedBond


def compose_repayment_notification(
    bond_ticker: str, bond_name: str, payment: float, is_missed: bool
) -> str:
    return (
        f"Got repayment for `{bond_ticker}` {' (missed)' if is_missed else ''}\n"
        f'Name: "{bond_name}"\n'
        f"Payment: {payment:.2f}₽"
    )


def compose_coupon_notification(
    bond_ticker: str, bond_name: str, payment: float, is_missed: bool
) -> str:
    return (
        f"Got coupon for `{bond_ticker}` {' (missed)' if is_missed else ''}\n"
        f'Name: "{bond_name}"\n'
        f"Payment: {payment:.2f}₽"
    )


def compose_purchase_notification(
    bond: EnrichedBond,
    buy_quantity: int,
    buy_price: float,
    remaining_balance: float | None,
) -> str:
    return (
        f"Bought {buy_quantity} of `{bond.ticker}` ({bond.annual_yield:.2f}%)\n"
        f'Name: "{bond.name}"\n'
        f"Was available: {bond.ask_quantity}\n"
        f"Price: {buy_price:.2f}₽{f' ({buy_price / buy_quantity:.2f}₽ per bond)' if buy_quantity > 1 else ''}\n"
        f"Benefit: {bond.benefit * buy_quantity:.2f}₽ in {bond.days_to_maturity} days "
        f"({bond.benefit * buy_quantity / bond.days_to_maturity:.2f}₽ per day)\n"
        f"{f'Remaining balance: {remaining_balance:.2f}₽' if remaining_balance is not None else ''}"
    )
