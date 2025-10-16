import subprocess

def run_script(script):
    subprocess.run("python", script())

subprocess.run("python wallet_analyzer.py", shell=True) # Find top 100 traders of a token
subprocess.run("python dexwhales_scraper.py", shell=True) # Gather info about each trader to find the profitable wallets

