import requests
import mysql.connector
import time
from datetime import datetime



DB_PATH = "data/prices.db"

def connect():
    return mysql.connector.connect(
        host="sql7.freesqldatabase.com",
        user="sql7823353",
        password="uQe3haYPKV",
        database="sql7823353"
    )

def create_table():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        price FLOAT,
        timestamp DATETIME
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
    }

    print("Precios obtenidos:", prices)
    return prices


def save_prices(prices):
    conn = connect()
    cursor = conn.cursor()

    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    for name, price in prices.items():
        cursor.execute(
            "INSERT INTO crypto_prices (name, price, timestamp) VALUES (%s, %s, %s)",
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

        #Se ejecuta cada 60 segundos.
        time.sleep(60)


if __name__ == "__main__":
    main()
