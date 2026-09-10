# Flock Energy — Urja Meter Ops REST API Wrapper

A clean, maintainable, production-minded REST API wrapper built around the legacy **Urja Meter Ops** distribution metering portal (`https://urja-ops.flockenergy.tech`).

This service isolates the legacy SvelteKit web portal behind a clean, documented, normalized REST API. It handles portal session management, authentication lifecycle, CSRF header requirements, HTML/JSON parsing, value normalization, and error translation.

---

## 1. Architecture Overview

The system implements a strict **Adapter Pattern** with clean separation of concerns:

```
Client HTTP Request
       ↓
FastAPI Router (app/main.py)  ← Validation, Routes & Exception Handlers
       ↓
UrjaPortalClient (app/client.py)  ← Session Cookies, Auth Lifecycle & Single Retry
       ↓
Legacy Upstream Portal (https://urja-ops.flockenergy.tech)
       ↓
Parser & Normalizer (app/parser.py)  ← Pure Data Transformation & Value Normalization
       ↓
Pydantic Models (app/models.py)  ← Strict Public REST Data Contracts
       ↓
Clean REST JSON Response
```

### Architectural Principles
- **No Database / No Cache**: Operates as a pure stateless API wrapper ensuring real-time data freshness from the read-only upstream portal.
- **Strict Decoupling**: API routes contain zero scraping or BeautifulSoup logic. Network calls, data normalization, and public contracts are completely isolated.
- **Resilient Session Lifecycle**: Automatic session expiry detection with single re-authentication retry guarding against infinite loops.

---

## 2. Project Structure

```
FlockEnergyAssignment/
│
├── app/
│   ├── __init__.py        # Package initialization
│   ├── main.py            # FastAPI application & REST endpoint routes
│   ├── client.py          # UrjaPortalClient (Session management, Auth, Retries)
│   ├── models.py          # Pydantic schemas (Request/Response API contracts)
│   ├── config.py          # Environment configuration settings
│   ├── parser.py          # Pure parsing & data normalization logic
│   └── exceptions.py      # Domain exceptions and FastAPI exception handlers
│
├── tests/
│   ├── __init__.py        # Test package initialization
│   ├── test_api.py        # Integration tests for FastAPI endpoints
│   ├── test_parser.py     # Unit tests for data normalizer functions
│   └── test_client.py     # Unit tests for UrjaPortalClient HTTP lifecycle
│
├── PROTOCOL.md            # Reverse-engineered legacy portal protocol specification
├── REFLECTION.md          # 5-question honest engineering reflection
├── README.md              # Main project front-door documentation
├── openapi.json           # Exported OpenAPI 3.0 specification schema
├── requirements.txt       # Python project dependencies
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore rules
└── pyproject.toml         # Package build & pytest configuration
```

---

## 3. Requirements & Setup

### Prerequisites
- Python 3.10 or higher

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Roshini311/FlockEnergyAssignment.git
   cd FlockEnergyAssignment
   ```

2. **Create and activate a virtual environment**:
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 4. Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

`.env` content template:
```env
URJA_BASE_URL=https://urja-ops.flockenergy.tech/
URJA_USERNAME=
URJA_PASSWORD=
REQUEST_TIMEOUT=10.0
```

> [!IMPORTANT]
> Never commit `.env` or real credentials to source control. `.env` is listed in `.gitignore`.

---

## 5. Running the API Server

Start the API server with Uvicorn:

```bash
uvicorn app.main:app --reload --port 8000
```

The service will be accessible at `http://localhost:8000`.

- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **OpenAPI JSON Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 6. REST API Endpoints & Sample Requests

### 1. Health Check (Readiness / Liveness)
`GET /health`
Verifies API readiness and reports the configured target upstream portal URL.
```bash
curl http://localhost:8000/health
```
**Sample Response**:
```json
{
  "status": "ok",
  "upstream_portal": "https://urja-ops.flockenergy.tech"
}
```

---

### 2. Authenticate
`POST /api/v1/auth/login`
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@flockenergy.tech", "password": "your_password"}'
```
**Sample Response**:
```json
{
  "authenticated": true,
  "message": "Successfully authenticated with Urja Meter Ops portal."
}
```

---

### 3. List Smart Meters
`GET /api/v1/meters?q={search_term}&page=1&page_size=20`
```bash
curl "http://localhost:8000/api/v1/meters?page=1&page_size=20"
```
**Sample Response**:
```json
{
  "data": [
    {
      "meter_id": "MTR-1001",
      "serial_number": "SN-9988",
      "make": "Genus",
      "phase_type": "3-Phase",
      "install_status": "Installed",
      "dt_code": "DT-501"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_records": 45,
    "total_pages": 3
  }
}
```

---

### 4. Get Meter Details
`GET /api/v1/meters/{meter_id}`
```bash
curl http://localhost:8000/api/v1/meters/MTR-1001
```
**Sample Response**:
```json
{
  "meter_id": "MTR-1001",
  "hierarchy": {
    "Zone": "North",
    "Circle": "Circle-A",
    "Division": "Div-1",
    "DT": "DT-501"
  },
  "nameplate": [
    {"label": "CT Ratio", "value": "100/5"},
    {"label": "Accuracy Class", "value": "0.5s"}
  ],
  "location": {
    "latitude": 28.6139,
    "longitude": 77.2090
  }
}
```

---

### 5. Get Meter Energy Consumption
`GET /api/v1/meters/{meter_id}/consumption`
```bash
curl http://localhost:8000/api/v1/meters/MTR-1001/consumption
```
**Sample Response**:
```json
{
  "meter_id": "MTR-1001",
  "data": [
    {
      "timestamp": "2026-09-10T10:00:00Z",
      "kwh": 15.4,
      "kvah": 16.1,
      "volt_r": 230.5
    }
  ]
}
```

---

### 6. Get Network Hierarchy (Distribution Transformers)
`GET /api/v1/hierarchy?page=1&page_size=20`
```bash
curl "http://localhost:8000/api/v1/hierarchy?page=1&page_size=20"
```
**Sample Response**:
```json
{
  "data": [
    {
      "code": "DT-501",
      "name": "DT Central Market",
      "feeder_code": "F-01",
      "capacity_kva": 250.0
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_records": 12,
    "total_pages": 1
  }
}
```

---

## 7. Data Normalization Rules

- **Whitespace**: Stripped from all strings.
- **Ambiguous Nulls**: Strings like `"N/A"`, `"-"`, `"null"`, and `""` are normalized to `None`.
- **Numeric Integrity**: Values such as `"124.50"` are converted to `124.5`. "N/A" is **NEVER** converted to `0.0` to prevent data corruption.
- **Field Naming**: Legacy camelCase fields (`serialNo`, `dtCode`, `voltR`) are converted to clean REST snake_case (`serial_number`, `dt_code`, `volt_r`).

---

## 8. Testing

Run the test suite using `pytest`:

```bash
python -m pytest -v
```

### Test Coverage
- **Parser Unit Tests (`tests/test_parser.py`)**: Data cleaning, whitespace stripping, missing field handling, "N/A" conversion, and structural parsing.
- **Client Unit Tests (`tests/test_client.py`)**: Mocked upstream session lifecycle, CSRF header inclusion, login authentication failures, single-retry session expiration, network timeouts, and infinite loop guards.
- **API Integration Tests (`tests/test_api.py`)**: End-to-end FastAPI endpoint behavior, path parameter validation, Pydantic response contracts, and HTTP exception handlers (401, 404, 502, 504).

---

## 9. Deliverable Documents

- [PROTOCOL.md](file:///c:/Users/sanja/OneDrive/Desktop/flock_energy_assignment/PROTOCOL.md): Reverse-engineered legacy portal findings, endpoints, SvelteKit form actions, CSRF headers, and normalization mappings.
- [REFLECTION.md](file:///c:/Users/sanja/OneDrive/Desktop/flock_energy_assignment/REFLECTION.md): Honest 5-question engineering reflection detailing assumptions, challenges, mistakes, and future improvements.
- [openapi.json](file:///c:/Users/sanja/OneDrive/Desktop/flock_energy_assignment/openapi.json): Exported OpenAPI 3.0 specification matching the running FastAPI application.
