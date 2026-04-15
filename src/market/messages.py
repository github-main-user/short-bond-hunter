from src.market.schemas import NBond


def compose_maturity_notification(
    ticker: str,
    bond_name: str,
    principal: float,
    coupon: float | None,
    is_missed: bool = False,
) -> str:
    lines = [
        f"`{ticker}` matured{' (missed)' if is_missed else ''}",
        f"Name: {bond_name}",
        f"Principal: {principal:.2f}₽",
    ]
    if coupon is not None:
        lines.append(f"Coupon: {coupon:.2f}₽")
        lines.append(f"Total: {principal + coupon:.2f}₽")
    return "\n".join(lines)


def compose_late_coupon_notification(
    ticker: str, principal: float, coupon: float
) -> str:
    return (
        f"`{ticker}` late coupon received\n"
        f"Coupon: {coupon:.2f}₽\n"
        f"Total: {principal + coupon:.2f}₽"
    )


def compose_purchase_notification(
    bond: NBond, buy_quantity: int, buy_price: float, remaining_balance: float | None
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
