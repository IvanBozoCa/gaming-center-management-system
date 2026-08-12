# Gaming Center Management System

Backend para la administración de un gaming center/ciber.

El proyecto permitirá gestionar clientes, saldo de tiempo, estaciones,
sesiones de uso, pagos y posteriormente analítica del negocio.

## Tecnologías actuales

- Python
- FastAPI
- Uvicorn

## Requisitos

- Python 3.11 o superior

## Instalación

Clonar el repositorio y entrar al proyecto.

Crear el entorno virtual:

```bash
python -m venv .venv

```

## Activar el entorno en Windows PowerShell:
.\.venv\Scripts\Activate.ps1

## Instalar dependencias:
```bash
pip install -r requirements.txt

```
## Ejecutar el proyecto
uvicorn app.main:app --reload

La API estará disponible en:
http://127.0.0.1:8000

## Documentación
Swagger:
http://127.0.0.1:8000/docs

## Health Check
GET /health
Respuesta esperada:
{
  "status": "ok",
  "service": "gaming-center-api"
}