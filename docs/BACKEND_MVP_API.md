# Backend MVP API Contract

Referencia breve de los contratos HTTP disponibles para el frontend
administrativo del Gaming Center Management System.

La documentación completa y los schemas interactivos siguen disponibles
mediante Swagger en:

`/docs`

## Base local

Backend:

`http://127.0.0.1:8000`

Frontend Vite esperado:

`http://localhost:5173`

Los orígenes permitidos por CORS se configuran mediante
`CORS_ORIGINS`.

---

## Autenticación

La mayoría de las operaciones administrativas requieren:

`Authorization: Bearer <access_token>`

### Login

| Método | Endpoint | Auth | Propósito |
|---|---|---|---|
| POST | `/auth/login` | No | Obtener JWT |

El login utiliza `application/x-www-form-urlencoded` con:

- `username`
- `password`

Respuesta principal:

- `access_token`
- `token_type`

No existe refresh token en el MVP.

### Usuario autenticado

| Método | Endpoint | Auth | Propósito |
|---|---|---|---|
| GET | `/auth/me` | Bearer | Obtener usuario autenticado |

### Crear cliente

| Método | Endpoint | Auth | Propósito |
|---|---|---|---|
| POST | `/auth/register` | ADMIN | Registrar un CUSTOMER y crear su wallet |

---

## Clientes

| Método | Endpoint | Propósito |
|---|---|---|
| GET | `/admin/customers` | Listar y buscar clientes |
| GET | `/admin/customers/{customer_id}` | Obtener detalle de cliente |
| GET | `/admin/customers/{customer_id}/wallet` | Consultar saldo actual |
| GET | `/admin/customers/{customer_id}/time-transactions` | Consultar ledger de tiempo |
| POST | `/admin/customers/{customer_id}/time-purchases` | Acreditar tiempo |

Todos requieren rol `ADMIN`.

### Listado

`GET /admin/customers`

Filtros disponibles:

- `q`
- `is_active`
- `limit`
- `offset`

`limit` acepta valores entre `1` y `100`.

La respuesta es un array y el MVP **no devuelve total de registros**.

### Historial de tiempo

`GET /admin/customers/{customer_id}/time-transactions`

Paginación:

- `limit`
- `offset`

Los movimientos están ordenados desde el más reciente.

Los campos:

- `available_seconds_delta`
- `reserved_seconds_delta`

representan **segundos de tiempo**, no dinero.

### Compra de tiempo

`POST /admin/customers/{customer_id}/time-purchases`

La operación acredita tiempo a la wallet del cliente y genera un
movimiento auditable en el ledger.

Un cliente inactivo no puede recibir nuevas compras de tiempo.

---

## Estaciones

| Método | Endpoint | Propósito |
|---|---|---|
| GET | `/admin/stations` | Listar estaciones |
| POST | `/admin/stations` | Registrar estación |
| PATCH | `/admin/stations/{station_id}/status` | Cambiar estado operativo |

Estados relevantes:

- `AVAILABLE`
- `IN_USE`
- `MAINTENANCE`
- `OFFLINE`

`IN_USE` pertenece al ciclo de vida de las sesiones y no debe
asignarse manualmente desde el frontend.

Una estación con una sesión activa no puede cambiar manualmente
su estado operativo.

---

## Sesiones de clientes registrados

| Método | Endpoint | Propósito |
|---|---|---|
| POST | `/admin/sessions` | Iniciar sesión |
| GET | `/admin/sessions/active` | Consultar sesiones activas |
| GET | `/admin/sessions/history` | Consultar sesiones finalizadas |
| POST | `/admin/sessions/{session_id}/extend` | Extender tiempo |
| POST | `/admin/sessions/{session_id}/finish` | Finalizar sesión |

Todos requieren `ADMIN`.

### Inicio

Una sesión registrada requiere:

- estación
- cliente
- tiempo autorizado

El backend reserva el tiempo desde la wallet y cambia la estación a
`IN_USE` de forma transaccional.

### Sesiones activas

El tiempo restante se calcula en el servidor.

`time_state` puede ser:

- `RUNNING`
- `EXHAUSTED`

Una sesión `EXHAUSTED` continúa técnicamente `ACTIVE` hasta que sea
finalizada explícitamente.

### Historial

Filtros disponibles:

- `customer_id`
- `station_id`
- `limit`
- `offset`

Orden:

`ended_at DESC, id DESC`

La respuesta no incluye total de registros.

### Extensión

La extensión agrega segundos autorizados utilizando saldo disponible
del cliente.

### Finalización

La duración consumida se determina mediante el reloj del servidor.

El frontend no envía `ended_at` ni duración consumida.

---

## Sesiones GUEST

| Método | Endpoint | Propósito |
|---|---|---|
| POST | `/admin/guest-sessions` | Iniciar sesión guest prepaga |
| GET | `/admin/guest-sessions/active` | Consultar guest activas |
| GET | `/admin/guest-sessions/history` | Consultar historial guest |
| POST | `/admin/guest-sessions/{session_id}/finish` | Finalizar guest |

Una sesión GUEST:

- no crea `User`
- no crea `TimeWallet`
- no genera movimientos en `TimeTransaction`
- utiliza únicamente el tiempo autorizado para esa sesión

El tiempo restante también se deriva desde el reloj del servidor.

### Historial GUEST

Filtros disponibles:

- `station_id`
- `limit`
- `offset`

Orden:

`ended_at DESC, id DESC`

`unused_seconds` es informativo y no se acredita a ninguna wallet.

---
## Productos de tiempo

| Método | Endpoint | Propósito |
|---|---|---|
| POST | `/admin/time-products` | Crear producto de tiempo |
| GET | `/admin/time-products` | Listar productos |
| GET | `/admin/time-products/{time_product_id}` | Obtener detalle |
| PATCH | `/admin/time-products/{time_product_id}` | Actualizar producto |

Todos requieren rol `ADMIN`.

Un producto de tiempo representa una oferta comercial reutilizable con:

- `id`
- `name`
- `duration_seconds`
- `price_clp`
- `is_active`
- `created_at`
- `updated_at`

`duration_seconds` representa la cantidad de tiempo que posteriormente
podrá acreditarse o autorizarse.

`price_clp` representa el precio vigente del producto en pesos chilenos y
se almacena como entero.

Ejemplo:

```json
{
  "name": "1 hora",
  "duration_seconds": 3600,
  "price_clp": 2500
}
```

### Estados y edición

Los productos no se eliminan físicamente mediante esta API.

Un producto que deja de venderse debe actualizarse con:

```json
{
  "is_active": false
}
```

El listado acepta el filtro opcional:

`is_active`

Ejemplos:

`GET /admin/time-products?is_active=true`

`GET /admin/time-products?is_active=false`

Cambiar el precio o duración de un producto modifica su configuración
vigente. Las futuras ventas deberán almacenar sus propios snapshots de
precio y duración para que el historial no cambie retroactivamente.

### Alcance comercial actual

El catálogo de productos **no registra un pago ni una venta por sí solo**.

En esta etapa:

`TimeProduct` = definición de precio y tiempo.

Una historia posterior será responsable de transformar una selección de
producto en una venta y aplicar el tiempo correspondiente a una wallet
REGISTERED o a una sesión GUEST.
## Errores HTTP relevantes

El frontend debe tratar especialmente:

- `401 Unauthorized`: token inexistente, inválido, expirado o usuario inactivo.
- `403 Forbidden`: usuario autenticado sin permisos ADMIN.
- `404 Not Found`: recurso solicitado inexistente.
- `409 Conflict`: estado de negocio incompatible con la operación.
- `422 Unprocessable Entity`: parámetros o payload inválidos.

El campo público de error utilizado por FastAPI es normalmente:

```json
{
  "detail": "..."
}
```

---

## Decisiones del MVP

Antes de iniciar el frontend se consideran estables los contratos
descritos en este documento.

Quedan fuera del backend MVP actual:

- totales para paginación
- filtros por rango de fechas
- edición de clientes
- dashboard agregado
- exportaciones
- auto-finalización de sesiones agotadas
- heartbeat de estaciones
- WebSockets
- agente Windows
- pagos monetarios
- facturación

Estas funcionalidades deberán incorporarse como nuevas historias Scrum
sin modificar silenciosamente los contratos existentes.
