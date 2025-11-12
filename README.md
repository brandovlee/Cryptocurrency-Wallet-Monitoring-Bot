# Cryptocurrency Wallet Monitoring Bot

## Overview
CLI-based program that takes a Solana token address and computes trading metrics (win rate, profit/loss, average trade duration, and more).

## Purpose
1) Identify experienced, profitable traders on the Solana blockchain
2) Monitor their trades
3) Copy their trades
5) Repeat

## Example Usage
Given a wallet address, the program displays a complete trading summary to assess whether a trader is worth copying.
How profitable are they? Do they execute many short-term trades (possible bot) or hold long-term profitable positions?
This program provides all the statistics needed to answer these questions.

<img width="565" height="252" alt="crypto" src="https://github.com/user-attachments/assets/0a87af58-f84e-4fea-84c4-9c76e0b86032" />

## System Design

### `dexwhales_scraper.py`
Identifies potential traders to monitor.
- Scrapes the top 100 traders for a given Solana token address using [dexwhales.xyz](https://dexwhales.xyz/).
- Uses **Selenium** and **pyperclip** to capture wallet addresses directly from the site.
- Stores the extracted wallet addresses in a local **SQLite3 database**.

### `wallet_analyzer.py`
Analyzes wallet trading performance.
- Loads wallet addresses from the SQLite database and/or passed in at runtime via command line.
- Fetches up to 1,000 transactions per address via the **Solana RPC API**.
- Outputs the results as a short summary.
