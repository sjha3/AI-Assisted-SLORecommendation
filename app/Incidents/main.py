import logging
from typing import List

from fastapi import FastAPI, HTTPException, Query

try:
    from .logic import get_incidents_for_service_api_in_period
    from .model.incident_model import Incident
except ImportError:
    from logic import get_incidents_for_service_api_in_period
    from model.incident_model import Incident

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="Incidents API")


@app.get("/incidents", response_model=List[Incident])
def get_incidents(
    service_id: str = Query(...),
    api: str = Query(...),
    start_time: str = Query(..., description="ISO-8601 timestamp, e.g. 2026-03-01T00:00:00Z"),
    end_time: str = Query(..., description="ISO-8601 timestamp, e.g. 2026-03-01T23:59:59Z"),
):
    logger.info(
        "GET /incidents called with service_id=%s api=%s start_time=%s end_time=%s",
        service_id,
        api,
        start_time,
        end_time,
    )

    try:
        rows = get_incidents_for_service_api_in_period(
            service_id=service_id,
            api=api,
            start_time=start_time,
            end_time=end_time,
        )
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    if not rows:
        raise HTTPException(status_code=404, detail="No incidents found for the given service/api/time period")

    return rows
