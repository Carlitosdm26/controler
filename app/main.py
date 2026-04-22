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


# ------------------ CONEXIÓN ------------------

def connect():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# ------------------ CREACIÓN TABLAS ------------------

def create_tables():
    conn = connect()
    cursor = conn.cursor()

    # tabla de precios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        price FLOAT,
        created_at TIMESTAMP
    )
    """)

    # tabla de configuración de cryptos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_alert (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) UNIQUE,
        min_price FLOAT,
        max_price FLOAT,
        alerts_enabled BOOLEAN
    )
    """)

    # insertar bitcoin por defecto
    cursor.execute("""
    INSERT IGNORE INTO crypto_alert (name, min_price, max_price, alerts_enabled)
    VALUES ('bitcoin', 60000, 70000, TRUE)
    """)

    conn.commit()
    conn.close()


# ------------------ OBTENER CRYPTOS ------------------

def get_cryptos():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM crypto_alert")
    result = cursor.fetchall()

    conn.close()

    return [row[0] for row in result]


# ------------------ OBTENER CONFIG ALERTAS ------------------

def get_alert_config():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, min_price, max_price, alerts_enabled
        FROM crypto_alert
    """)

    rows = cursor.fetchall()
    conn.close()

    config = {}
    for row in rows:
        config[row[0]] = {
            "min": row[1],
            "max": row[2],
            "enabled": row[3]
        }

    return config


# ------------------ FETCH PRECIOS ------------------

def fetch_prices():
    cryptos = get_cryptos()

    if not cryptos:
        print("No hay criptos en la BDD")
        return {}

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(cryptos),
        "vs_currencies": "eur"
    }

    response = requests.get(url, params=params)
    data = response.json()

    prices = {}

    for crypto in cryptos:
        if crypto in data:
            prices[crypto] = data[crypto]["eur"]

    return prices


# ------------------ GUARDAR PRECIOS ------------------

def save_prices(prices):
    conn = connect()
    cursor = conn.cursor()
    timestamp = datetime.now(zhoraria)

    for name, price in prices.items():
        cursor.execute(
            "INSERT INTO crypto_prices (name, price, created_at) VALUES (%s, %s, %s)",
            (name, price, timestamp)
        )
        print(f"OK - INSERT {name}")

    print(f"Proceso de guardado en BDD: OK - {timestamp}")

    conn.commit()
    conn.close()


# ------------------ ALERTAS ------------------

def alerts(prices):
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
    YOUR_NUMBER = os.getenv("YOUR_NUMBER")

    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    config = get_alert_config()

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
        if name not in config:
            continue

        conf = config[name]

        if not conf["enabled"]:
            continue

        min_price = conf["min"]
        max_price = conf["max"]

        if max_price is not None and price > max_price:
            msg = f"🚀 {name} ha superado el MÁXIMO ({max_price}) → {price}"
            send_telegram(msg)

        elif min_price is not None and price < min_price:
            msg = f"📉 {name} ha bajado del MÍNIMO ({min_price}) → {price}"
            send_telegram(msg)


# ------------------ JOB ------------------

def job():
    timestamp = datetime.now(zhoraria)
    print(f"\nJOB EJECUTADO. {timestamp}")

    try:
        prices = fetch_prices()
        save_prices(prices)
        alerts(prices)

    except Exception as e:
        print("Error en el proceso:", e)


# ------------------ MAIN ------------------

def main():
    print("Iniciando tracker...")

    create_tables()

    job()

    schedule.every(1).minutes.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()