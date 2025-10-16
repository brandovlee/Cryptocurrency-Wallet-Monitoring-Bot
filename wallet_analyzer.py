import requests
from datetime import datetime, timezone, timedelta
import time
import sqlite3
import pandas as pd
import concurrent.futures
from dotenv import load_dotenv
import os

load_dotenv()

# Loads and returns the data as type list
def load_data():
    # Connect to the SQLite database
    db_file = os.getenv("DATAFILE_URL")
    conn = sqlite3.connect(db_file)
    data = pd.read_sql_query("SELECT * FROM wallets", conn) # Load wallets into the addresses variable
    conn.close() # Close the database connection

    # Convert data into a list
    df = pd.DataFrame(data)
    addresses = df['Address'].tolist()

    return addresses

# Sends an address to Solana API and returns up to 1000 transactions
def get_transactions(address, last_processed_signature=None):
    api_key = os.getenv("QUIKNODE_API_KEY")
    url = f"https://broken-methodical-cloud.solana-mainnet.quiknode.pro/{api_key}/"
    headers = {
        "Content-Type": "application/json"
    }
    params = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getConfirmedSignaturesForAddress2",
        "params": [
            address,
            {"limit": 1000}
        ]
    }
    
    if last_processed_signature:
        params["params"][1]["before"] = last_processed_signature

    # Send request to API and output an error if thrown
    try:
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()
        response_json = response.json()
        transactions = response_json.get("result", [])
        return transactions
    except requests.exceptions.RequestException as e:
        if response.status_code == 429:
            retry_after = response.headers
        return None

# Sends a transaction to the Solana RPC and returns transaction details
def get_batched_transaction_details(address, signatures):
    api_key = os.getenv("QUIKNODE_API_KEY")
    url = f"https://broken-methodical-cloud.solana-mainnet.quiknode.pro/{api_key}/"
    headers = {
        "Content-Type": "application/json"
    }
    params = [
        {
            "jsonrpc": "2.0",
            "id": idx,
            "method": "getTransaction",
            "params": [
                signature,
                {"maxSupportedTransactionVersion": 0}
            ]
        }
        for idx, signature in enumerate(signatures)
    ]

    # Send request to API and output an error if thrown
    try:
        response = requests.post(url, json=params, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        if response.status_code == 429:
            retry_after = response.headers
        return None

    response_json = response.json()

    # Process each response
    transaction_details = {}
    for response_item in response_json:
        result = response_item.get("result", {})
        signature = signatures[response_item["id"]]

        # Extracting the necessary details
        meta = result.get("meta", {})
        pre_balances = meta.get("preBalances", [])
        post_balances = meta.get("postBalances", [])
        pre_token_balances = meta.get("preTokenBalances", [])
        post_token_balances = meta.get("postTokenBalances", [])

        # Get the timestamp of the transaction
        block_time = result.get("blockTime", None)
        if block_time == None:
            continue
        transaction_time = datetime.fromtimestamp(block_time, tz=timezone.utc)  # Convert block_time to datetime

        # Skip if the address isn't in the account keys
        account_keys = result.get("transaction", {}).get("message", {}).get("accountKeys", [])
        if address in account_keys:
            wallet_index = account_keys.index(address)
        else:
            continue

        # Calculate net amount of SOL that was sold/bought
        net_amount_lamports = post_balances[wallet_index] - pre_balances[wallet_index]
        net_amount_sol = net_amount_lamports / 1_000_000_000  # Convert lamports to SOL

        # Extract token details for the specific wallet
        token_address = None
        pre_token_balance = 0
        post_token_balance = 0
        token_decimals = 0
        for pre_balance in pre_token_balances:
            if not pre_balance.get("owner"): # Error handling for instances with no owner
                token_address = None
                break
            if pre_balance["owner"] == address:
                token_address = pre_balance["mint"]
                pre_token_balance = int(pre_balance["uiTokenAmount"]["amount"])
                token_decimals = pre_balance["uiTokenAmount"]["decimals"]
                break
        if not token_address:
            for post_balance in post_token_balances:
                if not post_balance.get("owner"): # Error handling for instances with no owner
                    token_address = None
                    break
                if post_balance["owner"] == address:
                    token_address = post_balance["mint"]
                    post_token_balance = int(post_balance["uiTokenAmount"]["amount"])
                    token_decimals = post_balance["uiTokenAmount"]["decimals"]
                    break

        # Skip if it's wrapped sol or token address is none
        if token_address == "So11111111111111111111111111111111111111112" or token_address == None:
            continue

        # Calculate net amount of tokens that was sold/bought
        net_amount_tokens = (post_token_balance - pre_token_balance) / (10 ** token_decimals)
    
        # Store the transaction details if the transaction involves buying/selling a token
        if token_address != None and (abs(net_amount_sol) > 0.1):
            transaction_details[signature] = {
                "transaction_time": transaction_time,
                "net_amount_sol": net_amount_sol,
                "token_address": token_address,
                "net_amount_tokens": net_amount_tokens
            }

    return transaction_details

# Returns the winrate given the wins and losses
def calculate_winrate(wins, losses):
    total_trades = wins + losses
    winrate = (wins / total_trades) * 100 if total_trades > 0 else 0.0
    return winrate

# Returns the win/loss count, average profit/loss for all trades, and average profit/loss as a percentage
def calculate_average_profit_and_loss(trade_pnls, initial_investments):
    # Separate profits and losses
    profits = []
    losses = []
    win_count = 0
    loss_count = 0
    profits_pct = []
    losses_pct = []
    for pnl, initial_investment in zip(trade_pnls, initial_investments):
        if pnl > 0:
            profits.append(pnl)
            profits_pct.append((pnl / initial_investment) * 100)
            win_count += 1
        elif pnl < 0:
            losses.append(pnl)
            losses_pct.append((pnl / initial_investment) * 100)
            loss_count += 1

    # Calculate the average profit/loss per trade
    average_profit = sum(profits) / len(profits) if profits else 0
    average_loss = sum(losses) / len(losses) if losses else 0

    # Calculate the average profit/loss per trade as a percentage
    average_profit_pct = sum(profits_pct) / len(profits_pct) if profits_pct else 0
    average_loss_pct = sum(losses_pct) / len(losses_pct) if losses_pct else 0

    return average_profit, average_loss, average_profit_pct, average_loss_pct, win_count, loss_count

# Returns the winrate given the wins and losses
def calculate_winrate(wins, losses):
    total_trades = wins + losses
    winrate = (wins / total_trades) * 100 if total_trades > 0 else 0.0
    return winrate

# Returns the win/loss count, average profit/loss for all trades, and average profit/loss as a percentage
def calculate_average_profit_and_loss(trade_pnls, initial_investments):
    # Separate profits and losses
    profits = []
    losses = []
    win_count = 0
    loss_count = 0
    profits_pct = []
    losses_pct = []
    for pnl, initial_investment in zip(trade_pnls, initial_investments):
        if pnl > 0:
            profits.append(pnl)
            profits_pct.append((pnl / initial_investment) * 100)
            win_count += 1
        elif pnl < 0:
            losses.append(pnl)
            losses_pct.append((pnl / initial_investment) * 100)
            loss_count += 1

    # Calculate the average profit/loss per trade
    average_profit = sum(profits) / len(profits) if profits else 0
    average_loss = sum(losses) / len(losses) if losses else 0

    # Calculate the average profit/loss per trade as a percentage
    average_profit_pct = sum(profits_pct) / len(profits_pct) if profits_pct else 0
    average_loss_pct = sum(losses_pct) / len(losses_pct) if losses_pct else 0

    return average_profit, average_loss, average_profit_pct, average_loss_pct, win_count, loss_count

# Converts timedelta into human-readable format
def convert_timedelta(transaction_time):
    days = transaction_time.days
    seconds = transaction_time.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    return ", ".join(parts)

# Returns the average trade duration in human-readable format
def calculate_average_trade_duration(trade_durations):
    # Check if the list is empty
    if not trade_durations:
        return "No trades available"
    
    # Convert timedelta into total seconds
    total_seconds = [trade_duration.total_seconds() for trade_duration in trade_durations]

    # Calculate the average in seconds
    average_trade_duration_seconds = sum(total_seconds) / len(total_seconds)

    # Convert back to timedelta
    average_trade_duration = timedelta(seconds=average_trade_duration_seconds)

    # Convert into human-readable format
    return convert_timedelta(average_trade_duration)

# Returns all trading metrics of a a wallet
def compute_statistics(transaction_details_dict):
    buy_count = 0 # number of buys
    sell_count = 0 # number of sells
    total_pnl = 0.0 # total profit and loss
    unique_tokens = 0 # number of tokens traded
    token_holdings = {} # dictionary with token address as the key and contains the amount of holdings in SOL
    wins = 0 # number of wins
    losses = 0 # number of losses
    initial_investments = [] # list to store each trade's initial investment
    trade_pnls = [] # list to store each trade's PnL
    trade_durations = [] # list to store each trade's time duration
    position_sizes = [] # list to store the position sizes


    # Start at the transaction that happened first and iterate to most recent
    for transaction_detail in reversed(list(transaction_details_dict.values())):

        # Retrieve the transaction details
        transaction_time = transaction_detail.get("transaction_time", 0)
        net_amount_tokens = transaction_detail.get("net_amount_tokens", 0.0)
        net_amount_sol = transaction_detail.get("net_amount_sol", 0.0)
        token_address = transaction_detail.get("token_address", 0)

        # Determine if the transaction was a buy or sell then calculate average profit/loss using FIFO cost basis
        if net_amount_sol < 0: # Buy
            buy_count += 1

            if token_address not in token_holdings: # first time buying the token
                unique_tokens += 1 # update unique token count
                position_sizes.append(-net_amount_sol) # append transaction amount to position size list
                token_holdings[token_address] = {
                    "total_holdings": net_amount_tokens,
                    "cost_basis": [(transaction_time, net_amount_tokens, -net_amount_sol)] # (transaction_time, quantity, total cost)
                }

            else: # not first time buying the token
                position_sizes.append(-net_amount_sol)
                token_holdings[token_address]["total_holdings"] += net_amount_tokens # recalculate total holdings
                token_holdings[token_address]["cost_basis"].append((transaction_time, net_amount_tokens, -net_amount_sol)) # add cost basis

        elif net_amount_sol > 0 and token_address in token_holdings and token_holdings[token_address]["cost_basis"]:  # Sell
            sell_count += 1
            quantity_to_sell = -net_amount_tokens
            sell_date = transaction_time
            pnl = 0

            # Assume the price per token is derived from net_amount_sol / net_amount_tokens
            price_per_token = net_amount_sol / -net_amount_tokens if -net_amount_tokens > 0 else 0.0

            while quantity_to_sell > 0 and token_holdings[token_address]["cost_basis"]:
                purchase_date, purchase_quantity, purchase_cost = token_holdings[token_address]["cost_basis"].pop(0)

                if purchase_quantity == 0:
                    # Skip this purchase if the quantity is zero to avoid division by zero
                    continue

                if quantity_to_sell >= purchase_quantity:
                    # If selling more than or equal to the purchased quantity
                    pnl += purchase_quantity * (price_per_token - purchase_cost / purchase_quantity)
                    trade_pnls.append(pnl) # append pnl
                    initial_investments.append(purchase_cost)  # append initial investment
                    trade_durations.append(sell_date-purchase_date) # append trade duration
                    quantity_to_sell -= purchase_quantity # update quantity to sell
                else:
                    # If selling less than the purchased quantity
                    pnl += quantity_to_sell * (price_per_token - purchase_cost / purchase_quantity)
                    trade_pnls.append(pnl)
                    initial_investments.append(purchase_cost)
                    trade_durations.append(sell_date-purchase_date)
                    remaining_quantity = purchase_quantity - quantity_to_sell
                    token_holdings[token_address]["cost_basis"].insert(0, (sell_date, remaining_quantity, purchase_cost))
                    quantity_to_sell = 0

            token_holdings[token_address]["total_holdings"] -= -net_amount_tokens # recalculate token balance
            total_pnl += pnl

    # Calculates the average profit/loss and wins/losses
    (average_profit, average_loss, average_profit_pct, average_loss_pct, wins, 
     losses) = calculate_average_profit_and_loss(trade_pnls, initial_investments)

    # Calculates the winrate
    winrate = calculate_winrate(wins, losses)

    # Collect the active trades
    active_trades = {token: details for token, details in token_holdings.items() if details["cost_basis"]}

    # Calculate the average trade duration
    average_trade_duration = calculate_average_trade_duration(trade_durations)

    # Calculate the average position size
    average_position_size = sum(position_sizes) / len(position_sizes) if position_sizes else 0

    return (buy_count, sell_count, total_pnl, unique_tokens, winrate, 
            average_profit, average_loss, average_profit_pct, average_loss_pct, active_trades, 
            average_position_size, average_trade_duration)

# Function to get user choice for winrate selection
def get_winrate_selection(wallet_winrate_60, wallet_winrate_70, wallet_winrate_80):
    # Allow the user to select a winrate category to view addresses
    while True:
        print("\nSelect a winrate category to view addresses:")
        print(f"1. Winrate >= 80% ({len(wallet_winrate_80)} wallets)")
        print(f"2. Winrate >= 70% ({len(wallet_winrate_70)} wallets)")
        print(f"3. Winrate >= 60% ({len(wallet_winrate_60)} wallets)")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == '1':
            display_addresses(wallet_winrate_80)
        elif choice == '2':
            display_addresses(wallet_winrate_70)
        elif choice == '3':
            display_addresses(wallet_winrate_60)
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please select a valid option.")

# Function to display addresses based on user selection
def display_addresses(winrate_list):
    print("Addresses in the selected winrate category:")
    for wallet_info, address in winrate_list:
        display_stats(wallet_info, address)

# Function to display stats for a given wallet address
def display_stats(wallet_info, address):
    # Print the wallet info
    print("\nWallet Information:")
    print(f"Address: {address}")
    print(f"Latest transaction time: {wallet_info[address]['latest_transaction']}")
    print(f"Total Trades: {wallet_info[address]['total_trades']}")
    print(f"Winrate: {wallet_info[address]['winrate']}%")
    print(f"PnL: {wallet_info[address]['pnl']} SOL")
    print(f"Unique Tokens: {wallet_info[address]['unique_tokens']}")
    print(f"Buy Count: {wallet_info[address]['buy_count']}")
    print(f"Sell Count: {wallet_info[address]['sell_count']}")
    print(f"Average Profit: {wallet_info[address]['average_profit']}")
    print(f"Average Profit as Percentage: {wallet_info[address]['average_profit_pct']}%")
    print(f"Average Loss: {wallet_info[address]['average_loss']}")
    print(f"Average Loss as Percentage: {wallet_info[address]['average_loss_pct']}%")
    print(f"Average Trade Durations: {wallet_info[address]['average_trade_duration']}")
    print(f"Average Position Size: {wallet_info[address]['average_position_size']} SOL")

# Processes statistics for one wallet address
def process_address(address):
    try:
        # Initialize starting variables
        wallet_info = {}
        wallet_info[address] = {
            "total_trades": 0,
            "winrate": 0.0,
            "pnl": 0.0,
            "unique_tokens": 0,
            "buy_count": 0,
            "sell_count": 0,
            "average_profit": 0,
            "average_profit_pct": 0, 
            "average_loss": 0,
            "average_loss_pct": 0, 
            "average_trade_duration": 0,
            "average_position_size": 0,
            "latest_transaction": 0,
            "active_trades": 0
        }
        all_transactions = []
        last_processed_signature = None
        timeout = 60 # time it takes to timeout
        days = 300 # timeframe
        timeframe = datetime.now(timezone.utc) - timedelta(days=days) # timeframe

        start_time = time.time()
        while True:

            # Get the transactions that are tied to the wallet address
            raw_transactions = get_transactions(address, last_processed_signature)
            # Break if there are no transactions
            if not raw_transactions: 
                break

            # Fetch transaction details
            signatures = [txn["signature"] for txn in raw_transactions]
            transactions = get_batched_transaction_details(address, signatures) 

            # Break if there are no valid transactions
            if not transactions: 
                break

            # Exit if the transaction is out of timeframe
            exit_outer_loop = False
            for transaction in transactions.values():
                if transaction["transaction_time"] >= timeframe:
                    all_transactions.append(transaction)
                else:
                    exit_outer_loop = True
                    break
            if exit_outer_loop:
                break

            # Update last processed signature
            last_processed_signature = signatures[-1]

            end_time = time.time() - start_time # end time
            if end_time > timeout: # seconds
                print("Timed out") # throw error
                break

        # If there were no transactions, return empty wallet info
        if not all_transactions:
            return wallet_info, address

        # Create a dictionary from all_transactions
        transactions_dict = {txn["transaction_time"]: txn for txn in all_transactions}

        # Compute and update the final trading metrics of the wallet address
        (buy_count, sell_count, total_pnl, unique_tokens, winrate, 
            average_profit, average_loss, average_profit_pct, average_loss_pct, 
            active_trades, average_position_size, average_trade_duration) = compute_statistics(transactions_dict)
        
        # Get the latest transaction time
        latest_transaction_time = min(transactions_dict.keys())
        latest_transaction_human = latest_transaction_time.strftime("%Y-%m-%d %H:%M:%S %Z")

        # Update wallet info
        wallet_info[address].update({
            "total_trades": sell_count + buy_count,
            "winrate": round(winrate, 2),
            "pnl": round(total_pnl, 2),
            "unique_tokens": unique_tokens,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "average_profit": round(average_profit, 2),
            "average_profit_pct": round(average_profit_pct, 2), 
            "average_loss": round(average_loss, 2),
            "average_loss_pct": round(average_loss_pct, 2),
            "average_trade_duration": average_trade_duration,
            "average_position_size": round(average_position_size, 2),
            "latest_transaction": latest_transaction_human,
            "active_trades": active_trades
        })

        return wallet_info, address
    except Exception as e:
        print(f"Exception processing address {address}: {e}")
        return None, address

if __name__ == "__main__":
    # Load data
    addresses = load_data()
    addresses = []
    addresses.append(input("Input the wallet address that you want to check: "))

    # List to store potential wallets
    wallet_winrate_60 = []
    wallet_winrate_70 = []
    wallet_winrate_80 = []
    wallet_count = 0

    start_total_time = time.time() # start time to track total time

    # Use multiple threads to process each address
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future_to_address = {executor.submit(process_address, address): address for address in addresses}
        for future in concurrent.futures.as_completed(future_to_address): # Execute the addresses that have been checked
            wallet_info, address = future.result() # Store results
            wallet_count += 1 # Update wallet counter
            if wallet_info is None:
                print(f"No transactions found for this wallet: {address}")
                continue
                
            # Print the wallet info in a clean way
            print(f"Wallet Address: {address}")
            print(f"Total Trades: {wallet_info[address]['total_trades']}")
            print(f"Winrate: {wallet_info[address]['winrate']}%")
            print(f"PnL: {wallet_info[address]['pnl']} SOL")
            print(f"Unique Tokens: {wallet_info[address]['unique_tokens']}")
            print(f"Buy Count: {wallet_info[address]['buy_count']}")
            print(f"Sell Count: {wallet_info[address]['sell_count']}")
            print(f"Average Profit: {wallet_info[address]['average_profit']} SOL")
            print(f"Average Profit Percentage: {wallet_info[address]['average_profit_pct']}%")
            print(f"Average Loss: {wallet_info[address]['average_loss']}")
            print(f"Average Loss Percentage: {wallet_info[address]['average_loss_pct']}%")
            print(f"Average Trade Duration: {wallet_info[address]['average_trade_duration']}")
            print(f"Average Position Size: {wallet_info[address]['average_position_size']} SOL")
            print(f"Latest Transaction: {wallet_info[address]['latest_transaction']}")
            print(f"Active Trades: {wallet_info[address]['active_trades']}")
            print("-" * 50)

            # Add wallet to the proper winrate list
            if wallet_info[address]['winrate'] >= 80:
                wallet_winrate_80.append((wallet_info, address))
                wallet_winrate_70.append((wallet_info, address))
                wallet_winrate_60.append((wallet_info, address))
            elif wallet_info[address]['winrate'] >= 70:
                wallet_winrate_70.append((wallet_info, address))
                wallet_winrate_60.append((wallet_info, address))
            elif wallet_info[address]['winrate'] >= 60:
                wallet_winrate_60.append((wallet_info, address))

            print(f"Wallets checked: {wallet_count} / {len(addresses)}")

    end_total_time = time.time() - start_total_time # end time to track total time
    print(f"Total time to complete {end_total_time:.4f} seconds")
    
    # Determine which winrates to output
    get_winrate_selection(wallet_winrate_60, wallet_winrate_70, wallet_winrate_80)