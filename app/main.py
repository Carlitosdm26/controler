import requests
import mysql.connector
import time
from datetime import datetime
from zoneinfo import ZoneInfo

zhoraria = ZoneInfo("Europe/Madrid")
WITHELIST = {"bitcoin-cash"}
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
        "max": 380,
        "min": 360
    }
}


def connect():
    return mysql.connector.connect(
        host="sql7.freesqldatabase.com",
        user="sql7823404",
        password="RzwPNt58x2",
        database="sql7823404"
    )

def create_table():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        price FLOAT,
        timestamp TEXT
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

    TELEGRAM_TOKEN = "8316435201:AAE-Pvz6b1k8MKuSx9xlc2X7Me6WtazJP-w"
    CHAT_ID = "7550716847"

    def send_telegram(msg):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg
        })


    for name, price in prices.items():
        config = ALERT_THRESHOLDS.get(name)

        if config is None:
            continue

        if name not in WITHELIST:
            continue

        min_price = config["min"]
        max_price = config["max"]

        if price > max_price:
            msg = f"🚀 {name} ha superado el MÁXIMO ({max_price}) → {price}"
            print(msg)
            send_telegram(msg)

        elif price < min_price:
            msg = f"📉 {name} ha bajado del MÍNIMO ({min_price}) → {price}"
            print(msg)
            send_telegram(msg)




def main():
    print("Iniciando tracker...")

    create_table()

    while True:
        try:
            prices = fetch_prices()
            save_prices(prices)
            alerts(prices)
            print("Guardado correctamente\n")

        except Exception as e:
            print("Error:", e)

        #Se ejecuta cada 30 segundos.
        time.sleep(30)


if __name__ == "__main__":
    main()
