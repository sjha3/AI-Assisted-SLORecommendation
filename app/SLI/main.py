import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

try:
    from .model.sli_model import SLI
    from .logic import get_latest_sli_data, get_sli_data
except ImportError:
    from model.sli_model import SLI
    from logic import get_latest_sli_data, get_sli_data

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="SLI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/slis/latest", response_model=List[SLI])
def get_latest_sli(
    service_id: Optional[str] = Query(default=None),
    api: Optional[str] = Query(default=None),
):
    logger.info("GET /slis/latest called with service_id=%s api=%s", service_id, api)
    try:
        latest = get_latest_sli_data(service_id=service_id, api=api)
    except FileNotFoundError as ex:
        logger.warning("SLI source file missing: %s", ex)
        raise HTTPException(status_code=404, detail=str(ex)) from ex

    if not latest:
        raise HTTPException(status_code=404, detail="No SLI found for the given filters")

    logger.info("Returning %s latest SLI rows", len(latest))
    return latest


@app.get("/slis", response_model=List[SLI])
def get_slis(
    service_id: Optional[str] = Query(default=None),
    api: Optional[str] = Query(default=None),
    number_of_months: Optional[int] = Query(default=None, ge=1),
):
    logger.info(
        "GET /slis called with service_id=%s api=%s number_of_months=%s",
        service_id,
        api,
        number_of_months,
    )
    try:
        slis = get_sli_data(
            service_id=service_id,
            api=api,
            number_of_months=number_of_months,
        )
    except FileNotFoundError as ex:
        logger.warning("SLI source file missing: %s", ex)
        raise HTTPException(status_code=404, detail=str(ex)) from ex

    if not slis:
        raise HTTPException(status_code=404, detail="No SLI found for the given filters")

    logger.info("Returning %s rows for number_of_months=%s", len(slis), number_of_months)
    return slis
