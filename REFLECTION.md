# Flock Energy Take-Home Engineering Reflection

This document presents an honest engineering reflection on the implementation of the Urja Meter Ops REST API wrapper.

---

## 1. What assumptions did you make?

1. **Read-Only Portal Contract**: Assumed the upstream portal is strictly read-only. The API wrapper executes `GET` and `POST /login` requests only and performs zero destructive mutations against the legacy system.
2. **Session Lifetime & Expiry Mechanics**: Assumed portal sessions can expire unpredictably. Built `UrjaPortalClient` with an automatic session expiration check (`401` or login redirect) that triggers a single retry after re-authenticating.
3. **Pagination Defaults**: Assumed a standard default page size of 20 items for list endpoints based on the SvelteKit frontend UI grid parameters (`Math.ceil(total / 20)`).
4. **SvelteKit Route Conventions**: Assumed SvelteKit's standard data loading conventions (`/__data.json` for page data loads) remain consistent across application routes.

---

## 2. Which part was most difficult and how did you get unstuck?

**The Most Difficult Part**: Diagnosing SvelteKit's cross-site POST form submission check on `POST /login`.

When initial HTTP requests were dispatched to `POST /login`, the server returned `HTTP 403 Forbidden` with the error message: `Cross-site POST form submissions are forbidden`. 

**How I Got Unstuck**:
I inspected the SvelteKit client-side JavaScript bundles (`app.03ZTmlg3.js` and `DHWw2r--.js`) to trace form actions and CSRF handling. I recognized that modern SvelteKit server actions validate the HTTP `Origin` header against the host domain to prevent cross-site request forgery. By injecting `Origin: https://urja-ops.flockenergy.tech` into `httpx` headers, the authentication call succeeded cleanly.

---

## 3. If you had another day, what would you improve?

1. **Async `httpx.AsyncClient` Session Integration**: Migrate `UrjaPortalClient` to `httpx.AsyncClient` for fully non-blocking asynchronous I/O across high-concurrency FastAPI routes.
2. **Circuit Breaker Pattern**: Implement a resilience pattern (e.g. using `tenacity` or custom circuit breaker) to short-circuit requests when the upstream portal is experiencing prolonged outages or 5xx errors.
3. **In-Memory TTL Caching**: Add short-lived TTL caching (e.g. 30 seconds for meter metadata) to eliminate redundant upstream calls for high-frequency client requests.

---

## 4. What mistake did you make?

**The Mistake**: Assuming standard HTTP status code conventions for invalid authentication.

During initial client development, I expected `POST /login` to return an `HTTP 401 Unauthorized` status code when invalid credentials were provided. However, live testing revealed that SvelteKit's server action returned `HTTP 200 OK` containing an inline JSON failure envelope:
```json
{"type": "failure", "status": 401, "data": "[..., \"Invalid email or password.\"]"}
```

**Correction & Insight**:
I refactored `UrjaPortalClient.login()` to inspect both HTTP status codes and the response body content for SvelteKit action error payloads (`"type": "failure"`), preventing silent false-positive logins.

---

## 5. What would you criticize in your own submission?

1. **Synchronous `httpx.Client` Execution**: The current implementation uses synchronous `httpx.Client` calls inside standard FastAPI endpoint functions. While FastAPI executes synchronous endpoints in a threadpool to prevent blocking the main event loop, using native `httpx.AsyncClient` with `async def` routes would be even more resource-efficient under heavy load.
2. **Fallback Detail Parsing**: When fetching meter details, if SvelteKit's server load data format changes, the parser falls back to returning available hierarchy and geo data. While robust against total failure, explicitly logging structural parsing warnings would improve operational observability.
