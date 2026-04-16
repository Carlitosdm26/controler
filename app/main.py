import requests
import mysql.connector
import time
from datetime import datetime
from zoneinfo import ZoneInfo

zhoraria = ZoneInfo("Europe/Madrid")

ALERT_THRESHOLDS = {
    "bitcoin": {
        "max": 70000,
        "min": 65000
    },
    "ethereum": {
        "max": 3500,
        "min": 3000
    },
    "bitcoin-cash": {
        "max": 300,
        "min": 200
    }
}


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
        "ids": "bitcoin,ethereum,bitcoin-cash",
        "vs_currencies": "eur"
    }

    response = requests.get(url, params=params)
    data = response.json()

    prices = {
        "bitcoin": data["bitcoin"]["eur"],
        "ethereum": data["ethereum"]["eur"],
        "bitcoin-cash": data["bitcoin-cash"]["eur"]
    }

    #print("Precios obtenidos:", prices)
    return prices


def save_prices(prices):
    conn = connect()
    cursor = conn.cursor()

    timestamp = datetime.now(zhoraria).strftime("%d-%m-%Y %H:%M:%S")

    for name, price in prices.items():
        cursor.execute(
            "INSERT INTO crypto_prices (name, price, timestamp) VALUES (%s, %s, %s)",
            (name, price, timestamp)
        )

    conn.commit()
    conn.close()


def alerts(prices):
    print ("Procesando alertas...")

    for name, price in prices.items():
        config = ALERT_THRESHOLDS.get(name)

        if config is None:
            continue

        min_price = config["min"]
        max_price = config["max"]

        if price > max_price:
            print(f"🚀 {name} ha superado el MÁXIMO ({max_price}) → {price}")

        elif price < min_price:
            print(f"📉 {name} ha bajado del MÍNIMO ({min_price}) → {price}")




def main():
    print("Iniciando tracker...")

    create_table()

    while True:
        try:
            prices = fetch_prices()
            save_prices(prices)
            alerts(prices)
            #print("Guardado correctamente\n")

        except Exception as e:
            print("Error:", e)

        #Se ejecuta cada 60 segundos.
        time.sleep(60)


if __name__ == "__main__":
    main()
