import logging
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from model.deps_model import Dependency, DepsRequest, DepsResponse, BatchDepsCreateRequest
from logic import create_dependency, create_dependencies_batch, update_dependency, delete_dependency

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="Service API")


@app.post("/dependencies", status_code=201)
def create_service_endpoint(service_request: DepsRequest) -> DepsResponse:
    logger.info("Create service request received")
    try:
        response = create_dependency(dependency_request=service_request)
        logger.info("Service created successfully with Id=%s", response.Id)
        return response
    except ValueError as ex:
        logger.warning("Create service validation error: %s", ex)
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except FileExistsError as ex:
        logger.warning("Create service conflict: %s", ex)
        raise HTTPException(status_code=409, detail=str(ex)) from ex


@app.post("/dependencies/batch", status_code=201)
def create_dependencies_batch_endpoint(request: BatchDepsCreateRequest) -> List[DepsResponse]:
    logger.info("Batch dependency create API called with %s items", len(request.dependencies))
    if len(request.dependencies) == 0:
        raise HTTPException(status_code=400, detail="Batch must contain at least 1 dependency")

    try:
        responses = create_dependencies_batch(request.dependencies)
        logger.info("Batch dependency create succeeded with %s items", len(responses))
        return responses
    except ValueError as ex:
        logger.warning("Batch dependency validation error: %s", ex)
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except FileExistsError as ex:
        logger.warning("Batch dependency conflict: %s", ex)
        raise HTTPException(status_code=409, detail=str(ex)) from ex


@app.put("/dependencies/{dependency_id}")
def update_dependency_endpoint(dependency_request: DepsRequest, dependency_id: str) -> DepsResponse:
    logger.info("Update dependency request received for Id=%s", dependency_id)
    try:
        response = update_dependency(dependency_request=dependency_request, dependency_id=dependency_id)
        logger.info("Dependency updated successfully for Id=%s", response.Id)
        return response
    except ValueError as ex:
        logger.warning("Update dependency validation error for Id=%s: %s", dependency_id, ex)
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except FileNotFoundError as ex:
        logger.warning("Update dependency not found for Id=%s: %s", dependency_id, ex)
        raise HTTPException(status_code=404, detail=str(ex)) from ex



@app.delete("/dependencies/{dependency_id}")
def delete_dependency_endpoint(dependency_id: str) -> DepsResponse:
    logger.info("Delete dependency request received for Id=%s", dependency_id)
    try:
        response = delete_dependency(dependency_id=dependency_id)
        logger.info("Dependency deleted successfully for Id=%s", response.Id)
        return response
    except ValueError as ex:
        logger.warning("Delete dependency validation error for Id=%s: %s", dependency_id, ex)
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except FileNotFoundError as ex:
        logger.warning("Delete dependency not found for Id=%s: %s", dependency_id, ex)
        raise HTTPException(status_code=404, detail=str(ex)) from ex

