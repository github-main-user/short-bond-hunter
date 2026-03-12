from src.market.schemas import NBond


def compose_maturity_notification(ticker: str) -> str:
    return f"`{ticker}` matured"


def compose_purchase_notification(
    bond: NBond, buy_quantity: int, buy_price: float
) -> str:
    return (
        f"Bought {buy_quantity} of `{bond.ticker}` ({bond.annual_yield:.2f}%)\n"
        f"Available: {bond.ask_quantity}\n"
        f"Expected price: {bond.real_price * buy_quantity:.2f}₽\n"
        f"Actual price: {buy_price:.2f}₽ {f' ({buy_price / buy_quantity:.2f}₽ per bond)' if buy_quantity > 1 else ''}\n"
        f"Benefit: {bond.benefit * buy_quantity:.2f}₽ in {bond.days_to_maturity} days "
        f"({bond.benefit * buy_quantity / bond.days_to_maturity:.2f}₽ per day)"
    )
