from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import pyperclip
import sqlite3
from dotenv import load_dotenv
import os

load_dotenv()

# Returns the top 100 profitable traders given a token address using dexwhales
def scrape_date(url, token_address):
    options = Options()
    options.add_argument('--no-sandbox')
    driver = webdriver.Chrome(options=options)

    driver.get(url)

    # Enter token address into the search query
    enter_token_address = driver.find_element(By.XPATH, f'//*[@placeholder="Enter Token Address"]')
    enter_token_address.send_keys(token_address)

    time.sleep(2)

    # Submit search query
    find_trades_button = driver.find_element(By.XPATH, f'//button[text()="Find Traders"]')
    find_trades_button.click()

    time.sleep(2)

    # Find all elements that contain wallet addresses
    wallet_elements = driver.find_elements(By.XPATH, "//table/tbody/tr/td/span[@class='font-normal text-sm text-white hover:text-purple-300 cursor-pointer transition-colors duration-150']")

    # List to store the wallet addresses
    wallet_addresses = []

    # Iterate over each element and extract the text (wallet address)
    for wallet in wallet_elements:
        # Click on the address to copy to clipboard
        wallet.click()

        # Store the copied contents in a variable
        address = pyperclip.paste()

        # Append the address into the list
        wallet_addresses.append(address)

    driver.quit()

    return(wallet_addresses)

# Initialize database
def export_data_to_sq(wallet_addresses):
    # Connect to SQLite database (creates if not exists)
    db_file = os.getenv("DATAFILE_URL")
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    # Drop table if it already exists
    c.execute('DROP TABLE IF EXISTS wallets')

    # Create table to store data
    c.execute('''CREATE TABLE wallets (
                    Address TEXT
                 )''')
    
    # Insert the wallet addresses into the table
    for address in wallet_addresses:
        c.execute('''INSERT INTO wallets (Address)
                     VALUES (?)''',
                  (address,))
    
    # Commit changes and close connection
    conn.commit()
    conn.close()

# Gets the user input for the token address 
def get_token_address():
    # Allow the user to input a token address
    while True:
        
        token_address = input("Input the token address that you want to check: ")
        
        if len(token_address) == 44:
            return token_address
        else:
            print("Invalid input. Please try again.")


if __name__ == "__main__":
    # Initiliaze starting variables
    url = "https://dexwhales.xyz/"
    token_address = get_token_address()
    
    # Scrape the data from dexwhales
    wallet_addresses = scrape_date(url, token_address)

    # Store the data in sqlite3 database
    export_data_to_sq(wallet_addresses)

    if wallet_addresses:
        print(f"Successfully found top 100 traders for {token_address}.")
    else:
        print("Error fetching top 100 traders")