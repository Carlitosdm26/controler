import requests
import mysql.connector
import time
import schedule
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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
telegram_subscribers = set()
telegram_update_offset = None


def connect():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

def create_table(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        price FLOAT,
        timestamp TIMESTAMP
    )
""")

def fetch_prices():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,bitcoin-cash",
        "vs_currencies": "eur"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
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
    try:
        cursor = conn.cursor()
        timestamp = datetime.now(zhoraria)
        create_table(cursor)

        for name, price in prices.items():
            cursor.execute(
                "INSERT INTO crypto_prices (name, price, timestamp) VALUES (%s, %s, %s)",
                (name, price, timestamp)
            )
        conn.commit()
        print("Proceso de guardado en BDD: OK")
    finally:
        conn.close()


def send_telegram(telegram_token, chat_id, msg):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    response = requests.post(url, data={
        "chat_id": chat_id,
        "text": msg
    }, timeout=10)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram rechazó el mensaje: {result}")
    print("Telegram enviado:", msg)


def process_telegram_commands():
    global telegram_update_offset

    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        print("Telegram no configurado: define TELEGRAM_TOKEN")
        return

    params = {"timeout": 1}
    if telegram_update_offset is not None:
        params["offset"] = telegram_update_offset

    try:
        response = requests.get(
            f"https://api.telegram.org/bot{telegram_token}/getUpdates",
            params=params,
            timeout=5
        )
        response.raise_for_status()
        updates = response.json().get("result", [])
    except Exception as error:
        print("Error leyendo comandos de Telegram:", error)
        return

    for update in updates:
        telegram_update_offset = update["update_id"] + 1
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        command = message.get("text", "").strip().upper()

        if not chat_id:
            continue

        if command in {"SI", "SÍ"}:
            telegram_subscribers.add(chat_id)
            send_telegram(telegram_token, chat_id, "Alertas activadas.")
        elif command == "NO":
            telegram_subscribers.discard(chat_id)
            send_telegram(telegram_token, chat_id, "Alertas desactivadas.")


def alerts(prices):
    telegram_token = os.getenv("TELEGRAM_TOKEN")

    if not telegram_token:
        print("Telegram no configurado: define TELEGRAM_TOKEN")
        return

    if not telegram_subscribers:
        print("No hay chats suscritos a las alertas")
        return

    def send_alert(msg):
        for chat_id in tuple(telegram_subscribers):
            send_telegram(telegram_token, chat_id, msg)

    def send_sms(msg):
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_number = os.getenv("TWILIO_NUMBER")
        your_number = os.getenv("YOUR_NUMBER")
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=msg,
            from_=twilio_number,
            to=your_number
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
            send_alert(msg)

        elif price < min_price:
            msg = f"📉 {name} ha bajado del MÍNIMO ({min_price}) → {price}"
            #print(msg)
            #send_sms(msg)
            send_alert(msg)

def job():
    print("\n")
    try:
        prices = fetch_prices()
    except Exception as error:
        print("Error obteniendo precios:", error)
        return

    try:
        save_prices(prices)
    except Exception as error:
        print("Error guardando en la base de datos:", error)

    try:
        alerts(prices)
    except Exception as error:
        print("Error enviando alertas:", error)





def main():
    print("Iniciando tracker...")
    job()
    #schedule.every(1).minutes.do(job)
    schedule.every(30).seconds.do(job)
    while True:
        process_telegram_commands()
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
