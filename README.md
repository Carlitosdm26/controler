# controler

## Versión 1.0.0

### Novedades respecto a la versión anterior

Esta es la primera versión documentada del proyecto. Incluye:

- Configuración de criptomonedas, mínimos, máximos y estado de alertas desde MySQL.
- Consulta dinámica de las criptomonedas configuradas en `crypto_alert_configs`.
- Comandos `/start`, `/help`, `/activar`, `/desactivar`, `/lista`, `/suscribir` y `/desuscribir`.
- `/lista` muestra todos los usuarios registrados, su identificador, permisos de administrador y estado de alertas.
- Alertas de precio enviadas cada minuto, con registro separado de envíos correctos y fallidos.
- Visor web para consultar tablas MySQL desde el navegador.
- Gestión de errores para que un usuario de Telegram inválido no bloquee las alertas de los demás.

### Cambios de base de datos

- Se utiliza `crypto_alert_configs` para configurar las alertas sin modificar el código.
- La tabla contiene `name`, `min_price`, `max_price` y `enabled`.
- `crypto_prices` conserva el histórico de precios consultados.

## functions
Bot de Telegram para consultar precios de criptomonedas, guardarlos en MySQL y enviar alertas cuando se superan los umbrales configurados.

## Qué hace

- Consulta precios en EUR desde CoinGecko.
- Guarda cada consulta en la tabla `crypto_prices`.
- Ejecuta el trabajo de precios cada minuto.
- Registra en MySQL a cualquier usuario que escriba al bot.
- Guarda `username`, nombre y apellidos de cada usuario.
- Mantiene los permisos y el estado de las notificaciones en MySQL.
- Crea automáticamente las tablas necesarias si no existen.
- Evita iniciar una segunda instancia del bot desde `start.sh`.

Los nombres de las criptomonedas, sus umbrales y el estado de las alertas se configuran exclusivamente en MySQL.

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

## Visor web de la base de datos

Puedes abrir un visor sin registro para consultar tablas MySQL:

```bash
python3 app/db_viewer.py
```

Después abre `http://127.0.0.1:5000`. Introduce la dirección, puerto, usuario, contraseña y base de datos. El visor solo ejecuta consultas de lectura y muestra como máximo 200 filas por tabla. Las credenciales se mantienen únicamente en memoria durante la sesión y no se guardan en disco.

No expongas este visor directamente a Internet sin añadir autenticación y HTTPS. Para usarlo desde otro equipo, configura `WEB_HOST=0.0.0.0` y protégelo mediante un proxy seguro o una red privada.

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

### `crypto_alert_configs`

Guarda la configuración de las alertas por criptomoneda. El bot crea la tabla vacía si no existe. Añade las criptomonedas que quieras consultar y alertar:

```sql
INSERT INTO crypto_alert_configs (name, min_price, max_price, enabled)
VALUES
	('bitcoin', 60000, 70000, 1),
	('ethereum', 3000, 3500, 0),
	('bitcoin-cash', 350, 400, 1);
```

```sql
SELECT name, min_price, max_price, enabled
FROM crypto_alert_configs;

UPDATE crypto_alert_configs
SET min_price = 60000, max_price = 70000, enabled = 1
WHERE name = 'bitcoin';
```

### `telegram_subscribers`

Guarda una fila por chat de Telegram:

| Campo | Descripción |
| --- | --- |
| `id` | Identificador numérico autonumérico del usuario. |
| `chat_id` | Identificador único del chat de Telegram. |
| `username` | Nombre de usuario de Telegram, si existe. |
| `first_name` | Nombre del usuario. |
| `last_name` | Apellidos del usuario. |
| `is_admin` | `0` por defecto. Solo permite comandos administrativos cuando vale `1`. |
| `notifications_enabled` | `0` por defecto; `1` significa que recibe alertas. |
| `created_at` | Fecha de alta. |
| `updated_at` | Fecha de última modificación. |

Un usuario se registra aunque envíe un mensaje que el bot no reconozca. Los cambios manuales de `notifications_enabled` se vuelven a leer antes de cada ciclo de alertas, por lo que no es necesario reiniciar el bot.

### `telegram_messages`

Guarda los mensajes de texto que no son comandos, relacionados con el usuario mediante `user_id`:

| Campo | Descripción |
| --- | --- |
| `id` | Identificador autonumérico del mensaje. |
| `user_id` | `id` del usuario en `telegram_subscribers`. |
| `message` | Texto enviado por el usuario. |
| `created_at` | Fecha de recepción del mensaje. |

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

- `/start`: explica brevemente el funcionamiento del bot.
- `/help`: muestra los comandos disponibles.
- `/activar`: activa las alertas.
- `/desactivar`: desactiva las alertas, pero conserva al usuario en la base de datos.

### Administradores (`is_admin = 1`)

- `/lista`: muestra todos los usuarios registrados, sus datos identificativos y sus estados de administrador y alertas.
- `/suscribir <chat_id>`: activa las alertas para un chat.
- `/desuscribir <chat_id>`: desactiva las alertas de un chat sin borrar su registro.

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