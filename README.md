# Cryptocurrency Wallet Monitoring Bot
Analyzes Solana wallet trading performance by scraping blockchain data and computing key trading metrics such as win rate, profit/loss, average trade duration, and more.

## Overview
The project consists of two main scripts:

### `dexwhales_scraper.py`
- Scrapes the top 100 traders for a given Solana token address using [dexwhales.xyz](https://dexwhales.xyz/).
- Uses **Selenium** and **pyperclip** to capture wallet addresses directly from the site.
- Stores the extracted wallet addresses in a local **SQLite3 database**.

### `wallet_analyzer.py`
- Loads wallet addresses from the SQLite database and/or passed in at runtime via command line.
- Fetches up to 1,000 transactions per address via the **Solana RPC API** (configured through the `QUIKNODE_API_KEY`).
- Calculates statistics such as:
  - Total trades
  - Win rate
  - Average profit/loss (in SOL and %)
  - Average trade duration
  - Active positions and token holdings
- Outputs the results in a formatted console summary.