import logging

from . import calculators, plotters, printers
from .repositories import MaturityRepository, PurchaseRepository

logger = logging.getLogger(__name__)


def generate_report(group: str, plot: bool) -> None:
    df = calculators.per_purchase(
        PurchaseRepository().get_all(),
        MaturityRepository().get_all(),
    )

    match group:
        case "purchase":
            printers.print_per_purchase(df)
            if plot:
                plotters.plot_per_purchase(df)
        case "month":
            monthly = calculators.per_month(df)
            printers.print_per_month(monthly)
            if plot:
                plotters.plot_per_month(monthly)
        case "bond":
            bonds = calculators.per_bond(df)
            printers.print_per_bond(bonds)
            if plot:
                plotters.plot_per_bond(bonds)
