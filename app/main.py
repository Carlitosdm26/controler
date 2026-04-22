import requests
import mysql.connector
import time
import schedule
from datetime import datetime
from zoneinfo import ZoneInfo
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

    # PRIMERO crypto_alert
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_alert (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) UNIQUE,
        min_price FLOAT,
        max_price FLOAT,
        alerts_enabled BOOLEAN
    )
    """)

    # DESPUÉS crypto_prices
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        crypto_id INT,
        price FLOAT,
        created_at TIMESTAMP,
        FOREIGN KEY (crypto_id) REFERENCES crypto_alert(id)
    )
    """)

    # insertar bitcoin si no existe
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

    cursor.execute("SELECT id, name FROM crypto_alert")
    result = cursor.fetchall()

    conn.close()

    return result  # [(1, 'bitcoin'), (2, 'ethereum')]


# ------------------ CONFIG ALERTAS ------------------

def get_alert_config():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, min_price, max_price, alerts_enabled
        FROM crypto_alert
    """)

    rows = cursor.fetchall()
    conn.close()

    config = {}
    for row in rows:
        config[row[0]] = {
            "name": row[1],
            "min": row[2],
            "max": row[3],
            "enabled": row[4]
        }

    return config


# ------------------ FETCH PRECIOS ------------------

def fetch_prices():
    cryptos = get_cryptos()

    if not cryptos:
        return {}

    names = [c[1] for c in cryptos]

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(names),
        "vs_currencies": "eur"
    }

    response = requests.get(url, params=params)
    data = response.json()

    prices = {}

    for crypto_id, name in cryptos:
        if name in data:
            prices[crypto_id] = data[name]["eur"]

    return prices


# ------------------ GUARDAR PRECIOS ------------------

def save_prices(prices):
    conn = connect()
    cursor = conn.cursor()
    timestamp = datetime.now(zhoraria)

    for crypto_id, price in prices.items():
        cursor.execute(
            "INSERT INTO crypto_prices (crypto_id, price, created_at) VALUES (%s, %s, %s)",
            (crypto_id, price, timestamp)
        )
        print(f"OK - INSERT crypto_id={crypto_id}")

    print(f"Guardado OK - {timestamp}")

    conn.commit()
    conn.close()


# ------------------ ALERTAS ------------------

def alerts(prices):
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    config = get_alert_config()

    def send_telegram(msg):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg
        })
        print("Telegram enviado:", msg)

    for crypto_id, price in prices.items():
        if crypto_id not in config:
            continue

        conf = config[crypto_id]

        if not conf["enabled"]:
            continue

        name = conf["name"]
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
    print(f"\nJOB EJECUTADO: {timestamp}")

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