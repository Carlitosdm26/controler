import requests
import mysql.connector
import time
import schedule
from datetime import datetime
from zoneinfo import ZoneInfo
from twilio.rest import Client

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
    print("Proceso de guardado en BDD: OK")

    conn.commit()
    conn.close()


def alerts(prices):
    print ("Procesando alertas...")

    TELEGRAM_TOKEN = "8316435201:AAE-Pvz6b1k8MKuSx9xlc2X7Me6WtazJP-w"
    CHAT_ID = "7550716847"

    ACCOUNT_SID = "AC450ca4b09273b6996bff3cd5bf2c9e9e"
    AUTH_TOKEN = "d497e18e5f951c54d044d7c51f63429a"
    TWILIO_NUMBER = "+12182314043"   # número de Twilio
    YOUR_NUMBER = "+34645913563"   # tu móvil

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
    print("\n")
    try:
        prices = fetch_prices()
        save_prices(prices)
        alerts(prices)

    except Exception as e:
        print("Error:", e)





def main():
    print("Iniciando tracker...")
    job()
    #schedule.every(1).minutes.do(job)
    schedule.every(30).seconds.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
