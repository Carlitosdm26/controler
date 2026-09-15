import os
import re
import secrets

import mysql.connector
from flask import Flask, flash, redirect, render_template, request, session, url_for


app = Flask(__name__)
app.secret_key = os.getenv("WEB_SECRET_KEY", os.urandom(32))
MAX_ROWS = 200
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_$-]+$")
active_sessions = {}


def database_connection(credentials):
    return mysql.connector.connect(
        host=credentials["host"],
        port=credentials["port"],
        user=credentials["user"],
        password=credentials["password"],
        database=credentials["database"],
        connection_timeout=15,
        read_timeout=30,
        write_timeout=15,
    )


def valid_identifier(value):
    return bool(value and IDENTIFIER_PATTERN.fullmatch(value))


def credentials_from_form():
    host = request.form.get("host", "").strip()
    port_text = request.form.get("port", "3306").strip()
    user = request.form.get("user", "").strip()
    password = request.form.get("password", "")
    database = request.form.get("database", "").strip()

    try:
        port = int(port_text)
    except ValueError as error:
        raise ValueError("El puerto debe ser numérico.") from error

    if not host or not user or not database or not 1 <= port <= 65535:
        raise ValueError("Completa host, puerto, usuario y base de datos.")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def table_names(credentials):
    connection = database_connection(credentials)
    try:
        cursor = connection.cursor()
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def table_rows(credentials, table_name):
    if not valid_identifier(table_name):
        raise ValueError("Nombre de tabla no válido.")

    connection = database_connection(credentials)
    try:
        cursor = connection.cursor()
        order_clause = " ORDER BY id DESC" if table_name == "crypto_prices" else ""
        cursor.execute(f"SELECT * FROM `{table_name}`{order_clause} LIMIT {MAX_ROWS}")
        columns = [description[0] for description in cursor.description]
        return columns, cursor.fetchall()
    finally:
        connection.close()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            credentials = credentials_from_form()
            tables = table_names(credentials)
            session_token = secrets.token_urlsafe(32)
            active_sessions[session_token] = credentials
            session.clear()
            session["token"] = session_token
            session["tables"] = tables
            return redirect(url_for("index"))
        except Exception as error:
            flash(f"No se pudo conectar: {error}", "error")

    return render_template(
        "index.html",
        tables=session.get("tables", []),
        selected_table=None,
        columns=[],
        rows=[],
        max_rows=MAX_ROWS,
    )


@app.route("/table/<table_name>")
def show_table(table_name):
    credentials = active_sessions.get(session.get("token"))
    if not credentials:
        return redirect(url_for("index"))

    try:
        columns, rows = table_rows(credentials, table_name)
        return render_template(
            "index.html",
            tables=session.get("tables", []),
            selected_table=table_name,
            columns=columns,
            rows=rows,
            max_rows=MAX_ROWS,
        )
    except Exception as error:
        flash(f"No se pudo consultar la tabla: {error}", "error")
        return redirect(url_for("index"))


@app.post("/disconnect")
def disconnect():
    active_sessions.pop(session.get("token"), None)
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host=os.getenv("WEB_HOST", "127.0.0.1"), port=int(os.getenv("WEB_PORT", "5000")))
