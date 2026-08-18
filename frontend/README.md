# GCMS Admin Frontend

Administrative frontend for the Gaming Center Management System.

Built with React, TypeScript and Vite. It consumes the FastAPI backend and
provides administrative flows for customers, stations, REGISTERED sessions
and GUEST sessions.

## Requirements

- Node.js 22+
- npm 11+
- GCMS FastAPI backend running locally
- PostgreSQL configured for the backend

## Environment

Create the frontend environment file from the example:

```powershell
Copy-Item .env.example .env
```

Default local configuration:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

`VITE_API_BASE_URL` is required by the application.

## Install dependencies

From the `frontend` directory:

```powershell
npm install
```

## Run in development

First start the FastAPI backend from the repository root:

```powershell
uvicorn app.main:app --reload
```

Then, in another terminal:

```powershell
cd frontend
npm run dev
```

The frontend is normally available at:

```text
http://localhost:5173
```

The FastAPI backend is normally available at:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Administrative flows

The ADMIN frontend currently supports:

- ADMIN authentication and protected routes
- customer registration, search and filtering
- customer detail
- time wallet inspection
- time purchases
- time transaction ledger
- station registration and status management
- REGISTERED session start
- REGISTERED session extension
- REGISTERED session finish
- REGISTERED session history
- GUEST session start
- GUEST session finish
- GUEST session history

## Production validation

Run:

```powershell
npm run build
npm run lint
```

Both commands must pass before merging frontend changes.

The Vite production build is generated in:

```text
frontend/dist/
```

## Manual QA

The frontend administrative QA record is located at:

```text
docs/frontend-admin-qa.md
```

The smoke test covers:

- protected navigation
- login and logout
- invalid/expired authentication
- customer and wallet flows
- station status changes
- REGISTERED sessions
- GUEST sessions
- CORS integration
- controlled backend errors

## Local execution summary

Terminal 1:

```powershell
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Then open:

```text
http://localhost:5173
```