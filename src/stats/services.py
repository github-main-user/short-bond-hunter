import logging

from . import calculators, plotters, printers
from .repositories import MaturityRepository, PurchaseRepository

logger = logging.getLogger(__name__)


_REPORTS = {
    "purchase": (lambda df: df, printers.print_per_purchase, plotters.plot_per_purchase),
    "month": (calculators.per_month, printers.print_per_month, plotters.plot_per_month),
    "bond": (calculators.per_bond, printers.print_per_bond, plotters.plot_per_bond),
}


def generate_report(group: str, plot: bool) -> None:
    df = calculators.per_purchase(
        PurchaseRepository().get_all(),
        MaturityRepository().get_all(),
    )
    transform, printer, plotter = _REPORTS[group]
    data = transform(df)
    printer(data)
    if plot:
        plotter(data)
