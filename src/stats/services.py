import logging
from typing import cast

from .repository import StatsRepository

logger = logging.getLogger(__name__)


def generate_statistics():
    repo = cast(StatsRepository, StatsRepository())

    purchases = repo.get_all_purchases()
    maturities = repo.get_all_maturities()

    ticker_to_maturity = {m.bond_ticker: m for m in maturities}

    total_returned_bond = 0
    total_returned_tmon = 0

    for purchase in purchases:
        # assert if purchase.real_price and calculated manually real price don't match

        related_maturity = ticker_to_maturity.get(purchase.bond_ticker)
        if related_maturity is None:
            # logger.info(f"No related maturity found for bond: {purchase.bond_ticker}")
            continue

        maturity_quantity = related_maturity.principal_received / purchase.nominal
        return_per_bond = related_maturity.money_received / maturity_quantity

        if (
            purchase.tmon_price_at_buy is None
            or related_maturity.tmon_price_at_maturity is None
            or related_maturity.tmon_price_at_money_received is None
        ):
            # logger.info("TMON's price is None")
            continue

        # tmon per bond
        quantity_on_tmon = (
            purchase.real_price * purchase.quantity // purchase.tmon_price_at_buy
        )

        # TODO: use money_received_at instead of matured_at
        days = (related_maturity.matured_at.date() - purchase.bought_at.date()).days
        bond_annual_yield = (
            ((return_per_bond - purchase.real_price) / purchase.real_price)
            * (365.25 / days)
            * 100
            if days > 0 and purchase.real_price > 0
            else 0.0
        )
        tmon_annual_yield = (
            (
                (related_maturity.tmon_price_at_maturity - purchase.tmon_price_at_buy)
                / purchase.tmon_price_at_buy
            )
            * (365.25 / days)
            * 100
            if days > 0 and purchase.tmon_price_at_buy > 0
            else 0.0
        )
        returned_bond = (return_per_bond - purchase.real_price) * purchase.quantity
        returned_tmon = (
            related_maturity.tmon_price_at_maturity - purchase.tmon_price_at_buy
        ) * quantity_on_tmon

        print(
            f"\n{purchase.bond_ticker} (x{purchase.quantity}):"
            f" {purchase.bought_at.date()} -> {related_maturity.matured_at.date()}"
            f" ({days} days)"
            "\nBOND:"
            " ("
            f"spent: {purchase.real_price * purchase.quantity:.2f}₽,"
            f" return: {return_per_bond * purchase.quantity:.2f}₽,"
            f" total returned: {returned_bond:.2f}₽,"
            f" annual yield: {bond_annual_yield:.2f}%"
            ")"
            "\nTMON:"
            " ("
            f"spent: {related_maturity.tmon_price_at_maturity * quantity_on_tmon:.2f}₽,"
            f" return: {purchase.tmon_price_at_buy * quantity_on_tmon:.2f}₽,"
            f" total returned: {returned_tmon:.2f}₽,"
            f" annual yield: {tmon_annual_yield:.2f}%"
            ")",
        )
        total_returned_bond += returned_bond
        total_returned_tmon += returned_tmon

    print(
        "\n"
        + "=" * 40
        + (
            f"\nTotal returned BOND: {total_returned_bond:.2f}₽"
            f"\nTotal returned TMON: {total_returned_tmon:.2f}₽"
        )
    )
