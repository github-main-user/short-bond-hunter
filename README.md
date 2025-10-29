# Short Bond Hunter

This is a simple bot that automatically purchases bonds based on user-defined criteria: a minimum calculated annual yield and a maximum number of days to maturity.

The bot interacts with the Moscow Exchange (MOEX) through the T-Bank brokerage.


## Workflow

1.  **Fetch Bonds:** The bot retrieves a list of all available bonds from the exchange.
2.  **Filter Bonds:** It filters the bonds based on risk level (only "LOW" and "MEDIUM" risk bonds are considered) and the specified maximum days to maturity. This typically results in a small number of eligible bonds.
3.  **Subscribe to Order Book:** The bot subscribes to the order book for the filtered bonds to receive real-time price updates.
4.  **Calculate Yield and Place Orders:** With each price change, the bot recalculates the annual yield. If the yield meets the user-defined threshold, it places a market order to buy the bond.
5.  **Telegram Notifications (Optional):** You can configure the bot to send notifications to a Telegram channel by providing a valid bot token.

The bot periodically refreshes the list of bonds to ensure the maturity dates remain within the specified range.
You can also blacklist specific bonds by their ticker symbol to exclude them from trading.


## Getting Started

Before using the bot, you need to obtain an investment token from T-Bank: [https://developer.tbank.ru/invest/intro/intro/token](https://developer.tbank.ru/invest/intro/intro/token)


## Configuration

The bot is configured using environment variables. Copy the `.env.example` file to `.env` and fill in the values:

```bash
cp .env.example .env
```

Here's a description of the available environment variables:

*   `TINVEST_TOKEN`: Your T-Bank investment token. Obtain it from [https://developer.tbank.ru/invest/intro/intro/token](https://developer.tbank.ru/invest/intro/intro/token).
*   `TELEGRAM_BOT_TOKEN`: (Optional) Token for your Telegram chat bot, if you want to receive notifications.
*   `TELEGRAM_CHAT_ID`: (Optional) Your Telegram chat ID. To find it, send a message to your bot and then use `curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` in your terminal.


### Market Setup

*   `FEE_PERCENT`: Default brokerage fee in percent (e.g., `0.3` for 0.3%). It's recommended to switch to the "Trader" tariff for a 0.05% fee.
*   `DAYS_TO_MATURITY_MAX`: Maximum number of days to maturity for a bond to be considered.
*   `ANNUAL_YIELD_MIN`: Minimum annual yield in percent for a bond to be purchased.
*   `ANNUAL_YIELD_MAX`: Maximum annual yield in percent for a bond to be purchased.
*   `BOND_SUM_MAX`: Maximum total sum in RUB for bonds of a single ticker that the bot can hold.
*   `BOND_SUM_MAX_SINGLE`: Maximum sum in RUB for bonds of a single ticker per one deal.
*   `BLACK_LIST_TICKERS`: A JSON array of ticker symbols to exclude from trading (e.g., `'["RU000A105JN7", "RU000A10A3R1"]'`).


## Installation

There are two recommended ways to install the dependencies for this project.

### With `uv` (recommended)

If you have `uv` installed, you can install the dependencies directly from the `uv.lock` file.
This is the fastest and most reliable method.

```bash
uv sync
```

### With `pip`

If you prefer to use `pip`, you will need a `requirements.txt` file. The project does not ship with one, but you can generate it from the `pyproject.toml` file.

If you have `uv` installed, you can generate the `requirements.txt` file with the following command:

```bash
uv pip compile pyproject.toml -o requirements.txt
```

Once the `requirements.txt` file is created, you can install the dependencies using `pip`:

```bash
pip install -r requirements.txt
```
