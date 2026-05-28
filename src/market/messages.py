from src.market.domain import EnrichedBond


def compose_repayment_notification(
    bond_ticker: str, bond_name: str, payment: float
) -> str:
    return (
        f"Got repayment for `{bond_ticker}`\n"
        f'Name: "{bond_name}"\n'
        f"Payment: {payment:.2f}₽"
    )


def compose_coupon_notification(
    bond_ticker: str, bond_name: str, payment: float
) -> str:
    return (
        f'Got coupon for `{bond_ticker}`\nName: "{bond_name}"\nPayment: {payment:.2f}₽'
    )


def compose_purchase_notification(
    bond: EnrichedBond,
    buy_quantity: int,
    buy_price: float,
    remaining_balance: float | None,
) -> str:
    cost_without_commission = bond.current_price + bond.aci_value
    expected_maturity = bond.nominal + bond.coupons_sum
    return (
        f"{buy_price:.2f}₽, {bond.annual_yield:.2f}%, {bond.days_to_maturity}d\n"
        f"Ticker: `{bond.ticker}`\n"
        f'Name: "{bond.name}"\n'
        f"Qty Purchased: {buy_quantity} / {bond.ask_quantity}\n"
        f"Cost: {cost_without_commission * buy_quantity:.2f}₽ + {bond.commission * buy_quantity:.2f}₽ = {bond.real_price * buy_quantity:.2f}₽\n"
        f"Maturity: {bond.nominal * buy_quantity:.2f}₽ + {bond.coupons_sum * buy_quantity:.2f}₽ = {expected_maturity * buy_quantity:.2f}₽\n"
        f"Benefit: {bond.benefit * buy_quantity:.2f}₽ in {bond.days_to_maturity} days "
        f"({bond.benefit * buy_quantity / bond.days_to_maturity:.2f}₽ per day)\n"
        f"{f'Remaining balance: {remaining_balance:.2f}₽' if remaining_balance is not None else ''}"
    )
