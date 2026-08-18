# Frontend Admin QA

## SCRUM-148 — Navigation and authentication

- [x] Protected `/customers` route redirects unauthenticated users to `/login`
- [x] Protected `/stations` route redirects unauthenticated users to `/login`
- [x] Protected `/sessions` route redirects unauthenticated users to `/login`
- [x] Protected `/guest-sessions` route redirects unauthenticated users to `/login`
- [x] ADMIN login redirects to `/customers`
- [x] Authenticated access to `/login` redirects to `/customers`
- [x] Direct browser refresh works on protected routes
- [x] Sidebar navigation preserves the authenticated session
- [x] Logout removes access to protected routes
- [x] Invalid token / 401 clears the stored session
- [x] Unknown route renders the 404 page

## SCRUM-149 — Integrated smoke test

### Customer and wallet

- [x] Existing ACTIVE customer can be searched and opened
- [x] Time purchase updates the customer wallet
- [x] Time transaction history reflects the purchase

### Stations

- [x] AVAILABLE station can be changed to MAINTENANCE
- [x] MAINTENANCE station is not offered for session start
- [x] Station can be returned to AVAILABLE

### REGISTERED sessions

- [x] REGISTERED session can be started
- [x] Station changes to IN_USE
- [x] Active session exposes elapsed and remaining server snapshots
- [x] Active session can be extended
- [x] Session can be finished before exhaustion
- [x] Unused reserved time is released to the customer wallet
- [x] Finished session appears in REGISTERED history
- [x] Station returns to AVAILABLE

### GUEST sessions

- [x] GUEST session can be started
- [x] Station changes to IN_USE
- [x] GUEST session can be manually finished
- [x] consumed_seconds and unused_seconds are reported
- [x] Finished GUEST appears in history
- [x] EXHAUSTED GUEST remains active until explicit finish
- [x] Station returns to AVAILABLE after finish

### Integration

- [x] Frontend communicates with the local FastAPI backend
- [x] PostgreSQL state is reflected after frontend mutations
- [x] No browser CORS errors observed
- [x] 401 behavior validated in SCRUM-148
- [x] 404 responses are controlled
- [x] 409 conflicts are controlled
- [x] 422 validation errors are controlled
- [x] 403 role protection is covered by backend authorization tests

### Findings resolved during smoke

- [x] Customer detail link was present but `/customers/:customerId` was not registered in the router
- [x] Customer detail route now exposes account, wallet, time purchase and ledger
- [x] Session and GUEST `<select>` controls now use the shared dark form styling

## SCRUM-150 — Production build and execution

- [x] Frontend environment configuration documented
- [x] `VITE_API_BASE_URL` documented
- [x] Backend and frontend local startup documented
- [x] `npm run build` passes
- [x] `npm run lint` passes
- [x] Production `dist` directory is generated
- [x] Production build was validated with `npm run preview`
- [x] ADMIN login and main navigation work from the production preview
