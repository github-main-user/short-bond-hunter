import matplotlib.pyplot as plt
import pandas as pd


def plot_per_purchase(df: pd.DataFrame) -> None:
    ax = df.plot(
        x="received_at",
        y=["bond_yield", "tmon_yield"],
        kind="bar",
    )
    ax.set_xlabel("received at")
    ax.set_ylabel("annual yield %")
    plt.tight_layout()
    plt.show()


def plot_per_month(df: pd.DataFrame) -> None:
    ax = df.plot(
        y=["returned_bond", "returned_tmon"],
        kind="bar",
    )
    ax.set_xlabel("month")
    ax.set_ylabel("return ₽")
    plt.tight_layout()
    plt.show()


def plot_per_bond(df: pd.DataFrame) -> None:
    plot_df = df[["total_returned", "total_returned_tmon"]].copy()
    plot_df.index = [f"{ticker}\n{name}" for ticker, name in plot_df.index]
    ax = plot_df.plot(kind="bar")
    ax.set_xlabel("bond")
    ax.set_ylabel("return ₽")
    plt.tight_layout()
    plt.show()
