import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
'''
try:
    from .logic import (
        get_dependency_between,
        get_service_dependencies,
        store_dependencies_in_graph,
    )
    from .model.model import BatchDepsCreateRequest
except ImportError:
    from logic import (
        get_dependency_between,
        get_service_dependencies,
        store_dependencies_in_graph,
    )
    
    from app.DepsManager.model.model import BatchDepsCreateRequest
'''

from logic import (
        get_full_graph,
        get_dependency_between,
    get_downstream_nodes,
        get_service_dependencies,
        store_dependencies_in_graph,
    )
from model.model import BatchDepsCreateRequest
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="Dependencies Graph Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/graph/store", status_code=201)
def store_graph_endpoint(request: BatchDepsCreateRequest):
    logger.info("POST /graph/store called with %s dependency items", len(request.dependencies))
    if len(request.dependencies) == 0:
        raise HTTPException(status_code=400, detail="dependencies must contain at least one item")

    try:
        return store_dependencies_in_graph(request)
    except Exception as ex:
        logger.exception("Failed to store dependencies in graph DB: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.get("/graph/dependencies")
def get_dependencies_endpoint(service_id: str = Query(...)):
    logger.info("GET /graph/dependencies called for service_id=%s", service_id)
    try:
        return get_service_dependencies(service_id)
    except Exception as ex:
        logger.exception("Failed to query service dependencies: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.get("/graph/between")
def get_between_endpoint(
    source_service_id: str = Query(...),
    target_service_id: str = Query(...),
):
    logger.info(
        "GET /graph/between called for source=%s target=%s",
        source_service_id,
        target_service_id,
    )
    try:
        return get_dependency_between(source_service_id, target_service_id)
    except Exception as ex:
        logger.exception("Failed to query dependency relationship: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@app.get("/graph/all")
def get_graph_endpoint():
    logger.info("GET /graph/all called")
    try:
        return get_full_graph()
    except Exception as ex:
        logger.exception("Failed to fetch full graph: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex)) from ex

