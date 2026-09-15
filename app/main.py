import requests
import mysql.connector
import time
import schedule
import os
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

zhoraria = ZoneInfo("Europe/Madrid")
SUBSCRIBERS_FILE = Path(__file__).resolve().parent.parent / ".telegram_subscribers.json"
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
telegram_subscribers_meta = {}
telegram_update_offset = None
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "7550716847")


def connect():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
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


def save_telegram_subscribers():
    payload = {}
    for chat_id in sorted(telegram_subscribers):
        meta = telegram_subscribers_meta.get(str(chat_id), {})
        payload[str(chat_id)] = {
            "username": meta.get("username") or "",
            "first_name": meta.get("first_name") or "",
            "last_name": meta.get("last_name") or ""
        }
    SUBSCRIBERS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def get_subscriber_label(chat_id):
    meta = telegram_subscribers_meta.get(str(chat_id), {})
    username = (meta.get("username") or "").strip()
    first_name = (meta.get("first_name") or "").strip()
    last_name = (meta.get("last_name") or "").strip()

    if username and (first_name or last_name):
        full_name = " ".join(part for part in [first_name, last_name] if part)
        return f"@{username} ({full_name})"
    if username:
        return f"@{username}"
    if first_name or last_name:
        return " ".join(part for part in [first_name, last_name] if part)
    return f"chat_id={chat_id}"


def load_telegram_subscribers():
    if not SUBSCRIBERS_FILE.exists():
        save_telegram_subscribers()
        return

    try:
        subscribers = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
        if isinstance(subscribers, list):
            for chat_id in subscribers:
                chat_id = str(chat_id)
                telegram_subscribers.add(chat_id)
                telegram_subscribers_meta.setdefault(chat_id, {
                    "username": "",
                    "first_name": "",
                    "last_name": ""
                })
            return

        if isinstance(subscribers, dict):
            for chat_id, meta in subscribers.items():
                chat_id = str(chat_id)
                telegram_subscribers.add(chat_id)
                if isinstance(meta, dict):
                    telegram_subscribers_meta[chat_id] = {
                        "username": meta.get("username") or "",
                        "first_name": meta.get("first_name") or "",
                        "last_name": meta.get("last_name") or ""
                    }
                else:
                    telegram_subscribers_meta[chat_id] = {
                        "username": "",
                        "first_name": "",
                        "last_name": ""
                    }
    except (OSError, json.JSONDecodeError, TypeError):
        print(f"No se pudo leer {SUBSCRIBERS_FILE.name}")


def subscribe_telegram_chat(chat_id, sender=None):
    chat_id = str(chat_id)
    telegram_subscribers.add(chat_id)
    meta = telegram_subscribers_meta.setdefault(chat_id, {
        "username": "",
        "first_name": "",
        "last_name": ""
    })
    if sender:
        meta["username"] = sender.get("username") or meta.get("username") or ""
        meta["first_name"] = sender.get("first_name") or meta.get("first_name") or ""
        meta["last_name"] = sender.get("last_name") or meta.get("last_name") or ""
    save_telegram_subscribers()


def unsubscribe_telegram_chat(chat_id):
    chat_id = str(chat_id)
    if chat_id in telegram_subscribers:
        telegram_subscribers.discard(chat_id)
    telegram_subscribers_meta.pop(chat_id, None)
    save_telegram_subscribers()


def send_telegram(telegram_token, chat_id, msg, subscriber_label=None):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    response = requests.post(url, data={
        "chat_id": chat_id,
        "text": msg
    }, timeout=10)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram rechazó el mensaje: {result}")

    target = subscriber_label or f"chat_id={chat_id}"
    print(f"Telegram enviado a {target}: {msg}")


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
        text = message.get("text", "")
        command = text.strip().upper()

        if not chat_id:
            continue

        sender = message.get("from", {})
        username = sender.get("username") or "sin user"
        first_name = sender.get("first_name") or ""
        last_name = sender.get("last_name") or ""
        sender_name = " ".join(part for part in [first_name, last_name] if part).strip() or "sin nombre"
        sender_label = f"{username} | {sender_name}"

        if command == "/START":
            if chat_id == ADMIN_CHAT_ID:
                help_text = (
                    "👋 Bienvenido.\n\n"
                    "Comandos disponibles:\n"
                    "- SI / SÍ: activar alertas\n"
                    "- NO: desactivar alertas\n"
                    "- LISTA: ver suscriptores activos\n"
                    "- SUSCRIBIR <chat_id>: añadir un usuario manualmente\n"
                    "- DESUSCRIBIR <chat_id>: quitar un usuario manualmente"
                )
            else:
                help_text = (
                    "👋 Bienvenido.\n\n"
                    "Comandos disponibles:\n"
                    "- SI / SÍ: activar alertas\n"
                    "- NO: desactivar alertas"
                )
            send_telegram(telegram_token, chat_id, help_text)

        elif command == "LISTA":
            if chat_id != ADMIN_CHAT_ID:
                send_telegram(telegram_token, chat_id, "⛔ Solo el administrador puede usar este comando.")
                continue

            if not telegram_subscribers:
                send_telegram(telegram_token, chat_id, "📭 No hay suscriptores activos en este momento.")
                continue

            lines = ["📋 Suscriptores activos:"]
            for active_chat_id in sorted(telegram_subscribers, key=lambda x: str(x)):
                lines.append(f"- {get_subscriber_label(active_chat_id)} | chat_id={active_chat_id}")
            send_telegram(telegram_token, chat_id, "\n".join(lines))

        elif command.startswith("SUSCRIBIR "):
            if chat_id != ADMIN_CHAT_ID:
                send_telegram(telegram_token, chat_id, "⛔ Solo el administrador puede ejecutar este comando.")
                continue

            target_chat_id = command.replace("SUSCRIBIR ", "", 1).strip()
            if not target_chat_id:
                send_telegram(telegram_token, chat_id, "⚠️ Formato correcto: SUSCRIBIR <chat_id>")
                continue

            subscribe_telegram_chat(target_chat_id)
            send_telegram(telegram_token, chat_id, f"✅ Usuario suscrito manualmente: {target_chat_id}")
            print(f"Usuario suscrito manualmente: {target_chat_id} por {sender_label}")

        elif command.startswith("DESUSCRIBIR "):
            if chat_id != ADMIN_CHAT_ID:
                send_telegram(telegram_token, chat_id, "⛔ Solo el administrador puede ejecutar este comando.")
                continue

            target_chat_id = command.replace("DESUSCRIBIR ", "", 1).strip()
            if target_chat_id in telegram_subscribers:
                unsubscribe_telegram_chat(target_chat_id)
                send_telegram(telegram_token, chat_id, f"✅ Usuario desuscrito: {target_chat_id}")
                print(f"Usuario desuscrito manualmente: {target_chat_id} por {sender_label}")
            else:
                send_telegram(telegram_token, chat_id, f"⚠️ No existe ese suscriptor: {target_chat_id}")

        elif command in {"SI", "SÍ"}:
            subscribe_telegram_chat(chat_id, sender)
            print(f"Alertas activadas por {sender_label} (chat_id={chat_id})")
            send_telegram(telegram_token, chat_id, "✅ Alertas activadas. Recibirás avisos cuando cambie el precio.", subscriber_label=sender_label)
        elif command == "NO":
            unsubscribe_label = f"{username} | {sender_name}"
            unsubscribe_telegram_chat(chat_id)
            print(f"Alertas desactivadas por {unsubscribe_label} (chat_id={chat_id})")
            send_telegram(telegram_token, chat_id, "✅ Alertas desactivadas. Ya no recibirás avisos.", subscriber_label=unsubscribe_label)


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
            send_telegram(telegram_token, chat_id, msg, subscriber_label=get_subscriber_label(chat_id))

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
    load_telegram_subscribers()
    try:
        job()
        #schedule.every(1).minutes.do(job)
        schedule.every(30).seconds.do(job)
        while True:
            process_telegram_commands()
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nPrograma detenido por el usuario.")


if __name__ == "__main__":
    main()
