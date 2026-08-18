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

### Findings resolved during smoke

- [x] Customer detail link was present but `/customers/:customerId` was not registered in the router
- [x] Customer detail route now exposes account, wallet, time purchase and ledger
- [x] Session and GUEST `<select>` controls now use the shared dark form styling