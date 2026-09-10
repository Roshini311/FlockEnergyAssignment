# Urja Meter Ops Protocol Specification

This document provides a factual specification of the legacy **Urja Meter Ops** portal (`https://urja-ops.flockenergy.tech`) reverse-engineered during reconnaissance. It details authentication mechanics, session management, REST/SvelteKit data endpoints, pagination, response formats, quirks, and normalization rules.

---

## 1. Portal Overview

The Urja Meter Ops portal is built on **SvelteKit** serving a single-page application interface backed by internal REST data endpoints.

- **Base URL**: `https://urja-ops.flockenergy.tech`
- **Session Mechanism**: HTTP-Only Cookie Jar (e.g., `session` / `session_id`)
- **Content Types**: Form-urlencoded (`/login`), JSON (`/portal/*`), and SvelteKit Server Load JSON (`/__data.json`)

---

## 2. Authentication Protocol

### Endpoint Details
- **Path**: `POST /login`
- **Method**: `POST`
- **Content-Type**: `application/x-www-form-urlencoded`
- **Payload**:
  - `email`: string (e.g. `admin@flockenergy.tech`)
  - `password`: string

### CSRF & Origin Headers (Critical Security Constraint)
SvelteKit enforces cross-site POST protection. Any `POST /login` request missing an explicit origin header will fail:
- **Required Headers**:
  - `Origin: https://urja-ops.flockenergy.tech`
  - `Referer: https://urja-ops.flockenergy.tech/login`
- **Failure when missing**: Returns `HTTP 403 Forbidden` with plain-text body:
  `Cross-site POST form submissions are forbidden`

### Success Behavior
- Returns `HTTP 302 / 303 Redirect` or `HTTP 200 OK`
- Injects `Set-Cookie` header establishing an active authenticated session.

### Invalid Credentials Behavior
Returns `HTTP 200 OK` containing a SvelteKit failure JSON envelope:
```json
{
  "type": "failure",
  "status": 401,
  "data": "[{\"email\":1,\"error\":2},\"user@flockenergy.tech\",\"Invalid email or password.\"]"
}
```

---

## 3. Meter Search & Listing Protocol

- **Endpoint**: `GET /portal/meters/search`
- **Query Parameters**:
  - `q`: Search string (meter ID, serial number, etc.)
  - `page`: Integer page number (1-indexed, default `1`)
- **Authentication**: Required. Returns `HTTP 401 Unauthorized` if session is missing or expired:
  ```json
  {"error": "unauthorized", "message": "A valid session is required."}
  ```
- **Response Payload Format**:
  ```json
  {
    "data": [
      {
        "meterId": "MTR-1001",
        "serialNo": "SN-9988",
        "make": "Genus",
        "phaseType": "3-Phase",
        "installStatus": "Installed",
        "dtCode": "DT-501"
      }
    ],
    "total": 45
  }
  ```

---

## 4. Meter Details & Metadata Protocol

Fetching complete meter details involves two legacy calls:

1. **SvelteKit Load Data / Detail**:
   - **Path**: `GET /meters/{meter_id}/__data.json`
   - **Returns**: SvelteKit server load object containing:
     - `hierarchy`: Object mapping network levels (`Zone`, `Circle`, `Division`, `Subdivision`, `Sub Station`, `Feeder`, `DT`)
     - `detail`: Array or `classData` string containing nameplate parameters (e.g. `CT Ratio`, `Accuracy Class`, `Voltage Rating`)

2. **Geographic Location Sub-fetch**:
   - **Path**: `GET /portal/meters/{meter_id}/geo`
   - **Returns**:
     ```json
     {
       "data": {
         "latitude": 28.6139,
         "longitude": 77.2090
       }
     }
     ```

---

## 5. Meter Energy Consumption Protocol

- **Endpoint**: `GET /portal/meters/{meter_id}/energy`
- **Method**: `GET`
- **Authentication**: Required
- **Response Payload Format**:
  ```json
  {
    "data": [
      {
        "timestamp": "2026-09-10T10:00:00Z",
        "kwh": 15.40,
        "kvah": 16.10,
        "voltR": 230.5
      }
    ]
  }
  ```

---

## 6. Hierarchy Protocol (Distribution Transformers)

- **Endpoint**: `GET /portal/dts`
- **Query Parameters**:
  - `page`: Integer page number (1-indexed)
- **Response Payload Format**:
  ```json
  {
    "data": [
      {
        "code": "DT-501",
        "name": "DT Central Market",
        "feederCode": "F-01",
        "capacityKva": 250
      }
    ],
    "total": 12
  }
  ```

---

## 7. Discovered Quirks & Surprises

1. **CSRF Enforcement on Form POSTs**: SvelteKit's built-in origin check requires explicit `Origin` headers on non-browser HTTP clients.
2. **Inline HTTP 200 Failure Payloads**: Invalid credential attempts return HTTP 200 with an internal JSON error structure (`{"type": "failure", "status": 401, ...}`) rather than HTTP 401 status code at the transport level.
3. **Ambiguous Default Strings**: Fields without values return literal `"N/A"`, `"-"`, or `"null"` strings instead of JSON `null`.
4. **SvelteKit `__data.json` Hydration Routes**: SvelteKit exposes JSON endpoints for page server loads by appending `/__data.json` to page URLs.

---

## 8. Legacy Data Normalization Mapping

| Legacy Portal Field | Public REST API Field | Normalization & Transformation Rule |
| :--- | :--- | :--- |
| `meterId` | `meter_id` | Stripped string |
| `serialNo` | `serial_number` | Stripped string; `"N/A"` or `"-"` converted to `null` |
| `phaseType` | `phase_type` | Stripped string; `"N/A"` converted to `null` |
| `installStatus` | `install_status` | Stripped string |
| `dtCode` | `dt_code` | Stripped string |
| `feederCode` | `feeder_code` | Stripped string |
| `capacityKva` | `capacity_kva` | Parsed to float; `"N/A"` converted to `null` |
| `kwh` | `kwh` | Parsed to float; `"N/A"` converted to `null` (NOT 0.0) |
| `kvah` | `kvah` | Parsed to float; `"N/A"` converted to `null` |
| `voltR` | `volt_r` | Parsed to float; `"N/A"` converted to `null` |
| `latitude` | `latitude` | Parsed to float |
| `longitude` | `longitude` | Parsed to float |
