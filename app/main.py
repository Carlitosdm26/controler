import requests
import sqlite3
import time
from datetime import datetime

DB_PATH = "data/prices.db"

def create_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        timestamp TEXT
    )
    """)

    conn.commit()
    conn.close()


def fetch_prices():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum",
        "vs_currencies": "eur"
    }

    response = requests.get(url, params=params)
    data = response.json()

    prices = {
        "bitcoin": data["bitcoin"]["eur"],
        "ethereum": data["ethereum"]["eur"]
        "tether": data["tether"]["eur"]
        "ripple": data["ripple"]["eur"]
        "binancecoin": data["binancecoin"]["eur"]
        "usd-coin": data["usd-coin"]["eur"]
        "solana": data["solana"]["eur"]
        "tron": data["tron"]["eur"]
        "figure-heloc": data["figure-heloc"]["eur"]
        "dogecoin": data["dogecoin"]["eur"]
    }

    print("Precios obtenidos:", prices)
    return prices


def save_prices(prices):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    timestamp = datetime.now().isoformat()

    for name, price in prices.items():
        cursor.execute(
            "INSERT INTO crypto_prices (name, price, timestamp) VALUES (?, ?, ?)",
            (name, price, timestamp)
        )

    conn.commit()
    conn.close()


def main():
    print("Iniciando tracker...")

    create_table()

    while True:
        try:
            prices = fetch_prices()
            save_prices(prices)
            print("Guardado correctamente\n")

        except Exception as e:
            print("Error:", e)

        # esperar 1 hora (3600 segundos)
        time.sleep(3600)


if __name__ == "__main__":
    main()
