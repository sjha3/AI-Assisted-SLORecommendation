import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

try:
    from .logic import get_latest_slos_for_service, get_slos_for_service
    from .model.slo_model import SLO
except ImportError:
    from logic import get_latest_slos_for_service, get_slos_for_service
    from model.slo_model import SLO

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="Knowledge SLO API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/slos/service", response_model=List[SLO])
def get_service_slos(
    service_id: str = Query(...),
    api: Optional[str] = Query(default=None),
    slo_type: Optional[str] = Query(default=None),
):
    logger.info(
        "GET /slos/service called with service_id=%s api=%s slo_type=%s",
        service_id,
        api,
        slo_type,
    )
    try:
        rows = get_slos_for_service(service_id=service_id, api=api, slo_type=slo_type)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex

    if not rows:
        raise HTTPException(status_code=404, detail="No SLO found for the given filters")

    return rows


@app.get("/slos/service/latest", response_model=List[SLO])
def get_latest_service_slos(
    service_id: str = Query(...),
    api: Optional[str] = Query(default=None),
    slo_type: Optional[str] = Query(default=None),
):
    logger.info(
        "GET /slos/service/latest called with service_id=%s api=%s slo_type=%s",
        service_id,
        api,
        slo_type,
    )
    try:
        rows = get_latest_slos_for_service(service_id=service_id, api=api, slo_type=slo_type)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex

    if not rows:
        raise HTTPException(status_code=404, detail="No SLO found for the given filters")

    return rows
