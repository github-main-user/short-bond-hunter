# Short Bond Hunter

A bot that automatically trades short-maturity ruble bonds on the Moscow Exchange (MOEX)
through the T-Bank brokerage, based on user-defined criteria: a minimum calculated annual
yield and a maximum number of days to maturity.

It runs two independent strategies in parallel, tracks coupon and principal payments as
bonds mature, persists every purchase and payout to a local database, and can report your
realized performance against a money-market benchmark (the `TMON` ETF).


## Strategies

The bot continuously streams the order book for the eligible bonds and, on every price
change, runs both strategies:

- **Ask sniper** — buys immediately at the current ask with a market-like
  `FILL_OR_KILL` limit order whenever the annual yield falls in
  `[ASK_MIN_ANNUAL_YIELD, ASK_MAX_ANNUAL_YIELD]`. All-or-nothing: if the full order
  can't be filled instantly, it's cancelled entirely.
- **Bid waiter** — keeps a single resting limit bid one price-increment above the top
  bid whenever the projected yield falls in `[BID_MIN_ANNUAL_YIELD, BID_MAX_ANNUAL_YIELD]`.
  It places, replaces, or cancels the order as the book and yield move, and waits to be
  filled. Cheaper entry than the sniper, but no guarantee of execution.

Annual yield is computed from the full return (nominal + remaining coupons) against the
real all-in cost (price + accrued interest + commission), annualized over the days left
to maturity.


## Workflow

The session runs three concurrent streams:

1. **Order book stream** — fetches all eligible bonds, subscribes to their order books,
   and feeds every price tick to the ask sniper and bid waiter. Bonds are re-fetched
   every `BOND_REFRESH_INTERVAL_HOURS` to keep maturities, accrued interest, and the
   eligible set fresh.
2. **Maturity stream** — watches account operations for coupon and principal payments,
   records them, and (on repayment) refreshes resting bids since freed-up cash changes
   the affordable quantity.
3. **Order-state stream** — tracks resting bid orders, recording fills (full or partial)
   and removing cancelled/rejected orders from the registry.

Bonds are eligible only if they are RUB-denominated, non-perpetual, not qualified-investor
only, mature within `DAYS_TO_MATURITY_MAX` days, and carry **LOW** or **MEDIUM** risk.
You can also blacklist specific tickers via `BLACK_LISTED_TICKERS`.

Every purchase (tagged by strategy) and every maturity payout is written to a SQLite
database, along with the `TMON` ETF price at the time, so performance can later be compared
against simply holding a money-market fund. Telegram notifications are optional.


## Getting Started

Before using the bot, you need an investment token from T-Bank:
[https://developer.tbank.ru/invest/intro/intro/token](https://developer.tbank.ru/invest/intro/intro/token)


## Configuration

The bot is configured using environment variables. Copy `.env.example` to `.env` and fill
in the values:

```bash
cp .env.example .env
```

- `TINVEST_TOKEN`: Your T-Bank investment token.
- `TELEGRAM_BOT_TOKEN`: (Optional) Token for your Telegram bot, if you want notifications.
- `TELEGRAM_CHAT_ID`: (Optional) Your Telegram chat ID. To find it, send a message to your
  bot and run `curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`.

### Market setup

- `DAYS_TO_MATURITY_MAX`: Maximum days to maturity for a bond to be considered.
- `ASK_MIN_ANNUAL_YIELD` / `ASK_MAX_ANNUAL_YIELD`: Annual yield range (%) for the ask sniper.
- `BID_MIN_ANNUAL_YIELD` / `BID_MAX_ANNUAL_YIELD`: Annual yield range (%) for the bid waiter.
- `ASK_MAX_SUM_PER_BOND`: Maximum total RUB held per ticker by the ask sniper (shared cap).
- `ASK_MAX_SUM_PER_PURCHASE`: Maximum RUB per single ask-sniper purchase.
- `BID_MAX_SUM_PER_BOND`: Maximum total RUB per ticker held by the bid waiter.
- `BLACK_LISTED_TICKERS`: JSON array of tickers to exclude (e.g. `'["RU000A105JN7", "RU000A10A3R1"]'`).
- `BOND_REFRESH_INTERVAL_HOURS`: How often to re-fetch the bond list (default `4`).
- `BID_REGISTRY_SYNC_INTERVAL_SECONDS`: How often to reconcile active bids with the broker (default `1800`).


## Installation & Start

Install dependencies:

```bash
uv sync
```

Apply database migrations:

```bash
uv run alembic upgrade head
```

Run the bot:

```bash
uv run main.py
```


## Reports

After the bot has made some purchases, generate a performance report from the stored data:

```bash
uv run report.py <group> [--plot]
```

`<group>` is one of:

- `purchase` — one row per purchase.
- `month` — aggregated by month.
- `bond` — aggregated by bond.

Pass `--plot` to also render a chart.
