# SLI API - Usage Guide

This module exposes read-only GET APIs to query SLI data from `ServiceSLI.csv`.

## Run API

From `app/SLI`:

```powershell
uvicorn main:app --reload --port 8002
```

Base URL:

- `http://127.0.0.1:8002`

## Important

These are **GET** APIs, so they use **query parameters** (not request body).

---

## 1) Get latest SLI

Endpoint:

- `GET /slis/latest`

Query params:

- `service_id` (optional)
- `api` (optional)

### Example (service + api)

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8002/slis/latest?service_id=/subscription/3fff54f5-b78d-4d85-9db3-ff1ea74734c6/resourcegroup/3fff54f5-b78d-4d85-9db3-ff1ea74734dd/resourcetype/WebApp/resourcename/OrderService&api=orders/v1" -Method Get
```

### Example (api only)

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8002/slis/latest?api=payment/v1" -Method Get
```

---

## 2) Get SLI history by number of months

Endpoint:

- `GET /slis`

Query params:

- `service_id` (optional)
- `api` (optional)
- `number_of_months` (optional, integer >= 1)

Behavior:

- If `number_of_months` is not passed, API returns latest SLI row(s).
- If `number_of_months` is passed, API returns SLI rows from the latest timestamp going back that many months.

### Example (6 months for service + api)

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8002/slis?service_id=/subscription/3fff54f5-b78d-4d85-9db3-ff1ea74734c6/resourcegroup/3fff54f5-b78d-4d85-9db3-ff1ea74734dd/resourcetype/WebApp/resourcename/OrderService&api=orders/v1&number_of_months=6" -Method Get
```

### Example (3 months by api)

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8002/slis?api=customer-profile/v1&number_of_months=3" -Method Get
```

---

## Typical Response Fields

Each row is returned as:

- `ServiceId`
- `API`
- `Name`
- `Description`
- `Value`
- `Unit`
- `Window`
- `Timestamp`

## Common Errors

- `404` when no matching SLI rows are found for provided filters.
- `404` when `ServiceSLI.csv` is missing.
