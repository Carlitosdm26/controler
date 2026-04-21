import requests
import mysql.connector
import time
import schedule
from datetime import datetime
from zoneinfo import ZoneInfo
from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

zhoraria = ZoneInfo("Europe/Madrid")
WITHELIST = {"bitcoin-cash", "bitcoin"}
ALERT_THRESHOLDS = {
    "bitcoin": {
        "max": 70000,
        "min": 60000
    },
    "ethereum": {
        "max": 3500,
        "min": 3000
    },
    "bitcoin-cash": {
        "max": 400,
        "min": 350
    }
}


def connect():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

def create_table():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        price FLOAT,
        timestamp TIMESTAMP
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
    timestamp = datetime.now(zhoraria)
    create_table()

    for name, price in prices.items():
        cursor.execute(
            "INSERT INTO crypto_prices (name, price, timestamp) VALUES (%s, %s, %s)",
            (name, price, timestamp)
        )
        print(f"OK - INSERT {name}")
    print(f"Proceso de guardado en BDD: OK - {timestamp}" )

    conn.commit()
    conn.close()


def alerts(prices):
    #print ("Procesando alertas...")

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")   # número de Twilio
    YOUR_NUMBER = os.getenv("YOUR_NUMBER")   # tu móvil

    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    def send_telegram(msg):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg
        })
        print("Telegram enviado:", msg)

    def send_sms(msg):
        client.messages.create(
            body=msg,
            from_=TWILIO_NUMBER,
            to=YOUR_NUMBER
        )
        print("SMS enviado:", msg)


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
            #print(msg)
            #send_sms(msg)
            send_telegram(msg)

        elif price < min_price:
            msg = f"📉 {name} ha bajado del MÍNIMO ({min_price}) → {price}"
            #print(msg)
            #send_sms(msg)
            send_telegram(msg)

def job():
    timestamp = datetime.now(zhoraria)
    print(f"\nJOB EJECUTADO. {timestamp}")
    try:
        prices = fetch_prices()
        save_prices(prices)
        alerts(prices)

    except Exception as e:
        print("No se ha podido procesar", e)





def main():
    print("Iniciando tracker...")
    job()
    #schedule.every(1).minutes.do(job)
    schedule.every(1).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
