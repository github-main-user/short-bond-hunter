from src.market.domain import EnrichedBond, PriceView


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


def _compose_purchase_notification(
    bond: EnrichedBond,
    view: PriceView,
    qty: int,
    header: str,
    qty_line: str,
    remaining_balance: float | None,
) -> str:
    cost_without_commission = view.current_price + bond.aci_value
    return (
        f"{header}\n"
        f"Ticker: `{bond.ticker}`\n"
        f'Name: "{bond.name}"\n'
        f"{qty_line}\n"
        f"Cost: {cost_without_commission * qty:.2f}₽ + {view.commission * qty:.2f}₽ = {view.real_price * qty:.2f}₽\n"
        f"Maturity: {bond.nominal * qty:.2f}₽ + {bond.coupons_sum * qty:.2f}₽ = {bond.full_return * qty:.2f}₽\n"
        f"Benefit: {view.benefit * qty:.2f}₽ in {bond.days_to_maturity} days "
        f"({view.benefit * qty / bond.days_to_maturity:.2f}₽ per day)\n"
        f"{f'Remaining balance: {remaining_balance:.2f}₽' if remaining_balance is not None else ''}"
    )


def compose_ask_snipe_notification(
    bond: EnrichedBond,
    buy_quantity: int,
    buy_price: float,
    remaining_balance: float | None,
) -> str:
    ask = bond.ask
    return _compose_purchase_notification(
        bond,
        ask,
        buy_quantity,
        header=f"{buy_price:.2f}₽, {ask.annual_yield:.2f}%, {bond.days_to_maturity}d",
        qty_line=f"Qty Purchased: {buy_quantity} / {bond.ask_quantity}",
        remaining_balance=remaining_balance,
    )


def compose_bid_fill_notification(
    bond: EnrichedBond,
    view: PriceView,
    lots_filled: int,
    remaining_balance: float | None,
) -> str:
    return _compose_purchase_notification(
        bond,
        view,
        lots_filled,
        header=(
            f"BID FILLED: {view.real_price * lots_filled:.2f}₽, "
            f"{view.annual_yield:.2f}%, {bond.days_to_maturity}d"
        ),
        qty_line=f"Qty Filled: {lots_filled}",
        remaining_balance=remaining_balance,
    )
