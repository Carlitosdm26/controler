# controler
## functions
Bot de Telegram para consultar precios de criptomonedas, guardarlos en MySQL y enviar alertas cuando se superan los umbrales configurados.

## Qué hace

- Consulta precios en EUR desde CoinGecko.
- Guarda cada consulta en la tabla `crypto_prices`.
- Ejecuta el trabajo de precios cada 30 segundos.
- Registra en MySQL a cualquier usuario que escriba al bot.
- Guarda `username`, nombre y apellidos de cada usuario.
- Mantiene los permisos y el estado de las notificaciones en MySQL.
- Crea automáticamente las tablas necesarias si no existen.
- Evita iniciar una segunda instancia del bot desde `start.sh`.

Actualmente las alertas están activas para `bitcoin` y `bitcoin-cash`. Ethereum tiene umbrales definidos en el código, pero no está incluido en la lista activa de alertas.

## Requisitos

- Python 3.10 o superior.
- Una base de datos MySQL accesible desde el entorno donde se ejecuta el bot.
- Un bot de Telegram creado con [@BotFather](https://t.me/BotFather).
- Opcionalmente, una cuenta de Twilio para habilitar SMS si se activa esa parte del código.

## Instalación

```bash
git clone https://github.com/Carlitosdm26/controler.git
cd controler
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

También se puede iniciar con el script incluido:

```bash
chmod +x start.sh
./start.sh
```

`start.sh` instala las dependencias y no inicia otra instancia si ya encuentra un proceso ejecutando `python3 app/main.py`.

## Configuración

Crea un archivo `.env` en la raíz del proyecto. No lo subas al repositorio porque contiene credenciales.

```dotenv
TELEGRAM_TOKEN=123456789:token-del-bot

DB_HOST=tu-host-mysql
DB_PORT=3306
DB_USER=tu-usuario
DB_PASSWORD=tu-password
DB_NAME=tu-base-de-datos

# Opcional: credenciales de Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=tu-token-de-twilio
TWILIO_NUMBER=+34123456789
YOUR_NUMBER=+34600000000
```

Para Clever Cloud, utiliza el host, usuario, contraseña, nombre de base de datos y puerto que proporciona el servicio. El puerto no tiene por qué ser `3306`, así que debe copiarse expresamente en `DB_PORT`.

## Base de datos

El bot crea automáticamente estas tablas:

### `crypto_prices`

Guarda el nombre de la criptomoneda, su precio y la fecha de consulta.

### `telegram_subscribers`

Guarda una fila por chat de Telegram:

| Campo | Descripción |
| --- | --- |
| `chat_id` | Identificador único del chat de Telegram. |
| `username` | Nombre de usuario de Telegram, si existe. |
| `first_name` | Nombre del usuario. |
| `last_name` | Apellidos del usuario. |
| `is_admin` | `0` por defecto. Solo permite comandos administrativos cuando vale `1`. |
| `notifications_enabled` | `0` por defecto; `1` significa que recibe alertas. |
| `created_at` | Fecha de alta. |
| `updated_at` | Fecha de última modificación. |

Un usuario se registra aunque envíe un mensaje que el bot no reconozca. Los cambios manuales de `notifications_enabled` se vuelven a leer antes de cada ciclo de alertas, por lo que no es necesario reiniciar el bot.

Ejemplo para activar o desactivar alertas manualmente:

```sql
UPDATE telegram_subscribers
SET notifications_enabled = 1
WHERE chat_id = 123456789;

UPDATE telegram_subscribers
SET notifications_enabled = 0
WHERE chat_id = 123456789;
```

Todos los usuarios nuevos tienen `is_admin = 0`. Para conceder permisos administrativos, cambia el valor directamente en MySQL:

```sql
UPDATE telegram_subscribers
SET is_admin = 1
WHERE chat_id = 123456789;
```

## Comandos de Telegram

### Todos los usuarios

- `/start`: muestra los comandos disponibles.
- `SI` o `SÍ`: activa las alertas.
- `NO`: desactiva las alertas, pero conserva al usuario en la base de datos.

### Administradores (`is_admin = 1`)

- `LISTA`: muestra los usuarios activos y sus datos identificativos.
- `SUSCRIBIR <chat_id>`: activa las alertas para un chat.
- `DESUSCRIBIR <chat_id>`: desactiva las alertas de un chat sin borrar su registro.

Los mensajes distintos de estos comandos se registran en MySQL, pero no reciben respuesta del bot.

## Ejecución continua

El proceso debe permanecer ejecutándose para consultar precios y recibir mensajes de Telegram. `./start.sh` lo inicia en primer plano y protege contra una segunda instancia en el mismo entorno.

Para una ejecución permanente, utiliza un servicio que mantenga procesos activos, como un worker o servicio de fondo de tu proveedor cloud. Un terminal local o un contenedor de desarrollo no garantiza que el bot siga ejecutándose después de cerrar la sesión.

## Comprobaciones útiles

Comprobar que el código compila:

```bash
python3 -m py_compile app/main.py
```

Comprobar que el proceso está activo:

```bash
pgrep -af 'python3 app/main.py'
```

Comprobar usuarios y estado de alertas:

```sql
SELECT chat_id, username, first_name, last_name, is_admin, notifications_enabled
FROM telegram_subscribers
ORDER BY updated_at DESC;
```

## Solución de problemas

### El bot no conecta con MySQL

Comprueba `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` y `DB_NAME`. En servicios cloud, verifica especialmente el puerto proporcionado por el proveedor.

### Telegram muestra un conflicto `409 Conflict`

Hay más de una instancia usando el mismo token. Detén los procesos duplicados y vuelve a iniciar el bot con `./start.sh`.

### Un usuario no recibe alertas

Comprueba que su fila tenga `notifications_enabled = 1` y que la criptomoneda esté incluida en la lista activa de alertas.

### El bot no responde a un mensaje normal

Es el comportamiento esperado: los mensajes desconocidos se registran, pero solo se responde a los comandos definidos en esta documentación.

## Estructura

```text
.
├── app/
│   └── main.py
├── requirements.txt
├── start.sh
└── README.md
```