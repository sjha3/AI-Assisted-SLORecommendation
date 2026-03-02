# Service API (FastAPI)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment Variables (.env)

Create a `.env` file at the project root (`SLO_Recommendation/.env`) with the following values:

```dotenv
azure_endpoint=https://<your-resource-name>.openai.azure.com
azure_deployment=<your-model-deployment-name>
api_version=2025-01-01-preview
api_key=<your-azure-openai-api-key>
azure_model_name=<your-model-name>
```

These variables are used by `app/SLO_Recommend` to call Azure OpenAI and generate the `LLMExplanation` in `/slos/recommend`.

## Run

```powershell
cd .\app\Onb_API
uvicorn main:app --reload --port 8001

cd ..\SLI
uvicorn main:app --reload --port 8002

cd ..\DepsManager
uvicorn main:app --reload --port 8003

cd ..\SLO_Recommend
uvicorn main:app --reload --port 8007
```

## Data storage

The project uses file-based storage under `DB/`.

### `DB/` structure

- `DB/SLI/ServiceSLI.csv`
	- Historical SLI metrics per service/API.
	- Columns: `ServiceId`, `API`, `Type`, `Description`, `Value`, `Unit`, `Window`, `Timestamp`.
- `DB/SLO/ServiceSLO.json`
	- SLO targets coming from Knowledge Store per service/API/metric.
	- Used as current SLO source for impact analysis.
- `DB/DepGraph/service_dependency_graph.json`
	- Dependency graph used for recommendation and impact propagation.
	- Contains `nodes` and `edges` (`from_service_id`, `from_api`, `to_service_id`, `to_api`).
- `DB/Incidents/incidents.json`
	- Incident history used in SLO explanation and risk analysis.
	- Fields include `ServiceId`, `API`, `Type`, `Severity`, `Description`, `Timestamp`.
- `DB/Config/Service/*.json`
	- Service metadata/config (for example category lookup such as internal/external).
- `DB/Config/Deps/*.json`
	- Dependency configuration snapshots used by onboarding/dependency APIs.

## API Reference (all services in `app/`)

### 1) `app/Onb_API` (Service onboarding)

- `POST /services`
	- Create one service from `ServiceRequest`.
- `POST /services/batch`
	- Create multiple services from `{"services": [...]}`.
- `PUT /services/{service_id}`
	- Update a service by id.
- `DELETE /services/{service_id}`
	- Delete a service by id.

### 2) `app/Onb_Deps` (Dependency onboarding)

- `POST /dependencies`
	- Create one dependency from `DepsRequest`.
- `POST /dependencies/batch`
	- Create multiple dependencies from `{"dependencies": [...]}`.
- `PUT /dependencies/{dependency_id}`
	- Update a dependency by id.
- `DELETE /dependencies/{dependency_id}`
	- Delete a dependency by id.

### 3) `app/SLI` (SLI query)

- `GET /slis/latest`
	- Query params: `service_id` (optional), `api` (optional).
	- Returns latest timestamp SLI rows for the given filters.
- `GET /slis`
	- Query params: `service_id` (optional), `api` (optional), `number_of_months` (optional, `>=1`).
	- Returns historical SLI rows filtered by service/API/month window.

### 4) `app/Knowledge_SLO` (Known SLO query)

- `GET /slos/service`
	- Query params: `service_id` (required), `api` (optional), `slo_type` (optional).
	- Returns matching SLO rows.
- `GET /slos/service/latest`
	- Query params: `service_id` (required), `api` (optional), `slo_type` (optional).
	- Returns latest SLO rows per filter.

### 5) `app/DepsManager` (Dependency graph)

- `POST /graph/store`
	- Stores dependency edges into graph DB.
- `GET /graph/dependencies`
	- Query params: `service_id` (required).
	- Returns dependencies for one service.
- `GET /graph/between`
	- Query params: `source_service_id` (required), `target_service_id` (required).
	- Returns relationship/path summary between services.
- `GET /graph/all`
	- Returns full graph (`nodes` + `edges`).

### 6) `app/Incidents` (Incident query)

- `GET /incidents`
	- Query params:
		- `service_id` (required)
		- `api` (required)
		- `start_time` (required, ISO-8601)
		- `end_time` (required, ISO-8601)
	- Returns incidents for service/API in the given time range.

### 7) `app/SLO_Recommend` (Recommendation + impact + persistence)

- `GET /slos/recommend`
	- Query params: `service_id` (required), `api` (required)
	- Returns:
		- `Recommendations[]`
		- `SLIComparison[]`
		- `LLMExplanation`

- `POST /slos/impact-analysis`
	- Request body:
		- `ServiceId`, `API`, `NewSLO[]` (`Type`, `Target`, `Unit`)
	- Returns:
		- `UpstreamChain[]`
		- `AffectedNodes[]`
		- `LLMImpact`

- `POST /slos/recommended`
	- Saves accepted/user-provided recommended SLO to file storage.
	- Request body:
		- `ServiceId`, `API`, `SLOs[]` (`Type`, `Target`, `Unit`, `Window`)
	- Persistence:
		- Stored under `DB/RecommendedSLO`
		- One file per service+API, e.g. `CatalogService__catalog_v1.json`
		- New submissions append as timestamped entries.

### Example calls (PowerShell)

```powershell
# Recommend SLO
Invoke-RestMethod -Method GET "http://127.0.0.1:8008/slos/recommend?service_id=CheckoutService&api=checkout%2Fv1" |
	ConvertTo-Json -Depth 8

# Impact analysis
Invoke-RestMethod -Method POST "http://127.0.0.1:8008/slos/impact-analysis" `
	-ContentType "application/json" `
	-Body '{"ServiceId":"CheckoutService","API":"checkout/v1","NewSLO":[{"Type":"Availability","Target":99.5,"Unit":"percent"},{"Type":"Latency","Target":180.0,"Unit":"p95"},{"Type":"ErrorRate","Target":0.8,"Unit":"percent"}]}'

# Save accepted recommended SLO
Invoke-RestMethod -Method POST "http://127.0.0.1:8008/slos/recommended" `
	-ContentType "application/json" `
	-Body '{"ServiceId":"CatalogService","API":"catalog/v1","SLOs":[{"Type":"Availability","Target":99.9,"Unit":"percent","Window":"28"},{"Type":"Latency","Target":140,"Unit":"ms","Window":"28"},{"Type":"ErrorRate","Target":1.2,"Unit":"percent","Window":"28"}]}'
```
