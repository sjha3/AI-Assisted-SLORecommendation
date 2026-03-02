import logging
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from model.service_model import Service, ServiceRequest, ServiceResponse
from logic import create_service, create_services_batch, update_service, delete_service

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="Service API")


class BatchServiceCreateRequest(BaseModel):
    services: List[ServiceRequest]

    model_config = ConfigDict(extra="forbid")


@app.post("/services", status_code=201)
def create_service_endpoint(service_request: ServiceRequest) -> ServiceResponse:
    logger.info("Create service request received")
    try:
        response = create_service(service_request)
        logger.info("Service created successfully with Id=%s", response.Id)
        return response
    except ValueError as ex:
        logger.warning("Create service validation error: %s", ex)
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except FileExistsError as ex:
        logger.warning("Create service conflict: %s", ex)
        raise HTTPException(status_code=409, detail=str(ex)) from ex


@app.post("/services/batch", status_code=201)
def create_services_batch_endpoint(request: BatchServiceCreateRequest) -> List[ServiceResponse]:
    logger.info("Batch create API called with %s service requests", len(request.services))
    if len(request.services) == 0:
        raise HTTPException(status_code=400, detail="Batch must contain at least 1 service")

    try:
        responses = create_services_batch(request.services)
        logger.info("Batch create API succeeded with %s created services", len(responses))
        return responses
    except ValueError as ex:
        logger.warning("Batch create validation error: %s", ex)
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except FileExistsError as ex:
        logger.warning("Batch create conflict: %s", ex)
        raise HTTPException(status_code=409, detail=str(ex)) from ex


@app.put("/services/{service_id}")
def update_service_endpoint(service_request: ServiceRequest,service_id: str)-> ServiceResponse:
    logger.info("Update service request received for Id=%s", service_id)
    try:
        response = update_service(service_request, service_id)
        logger.info("Service updated successfully for Id=%s", response.Id)
        return response
    except ValueError as ex:
        logger.warning("Update service validation error for Id=%s: %s", service_id, ex)
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except FileNotFoundError as ex:
        logger.warning("Update service not found for Id=%s: %s", service_id, ex)
        raise HTTPException(status_code=404, detail=str(ex)) from ex



@app.delete("/services/{service_id}")
def delete_service_endpoint(service_id: str) -> ServiceResponse:
    logger.info("Delete service request received for Id=%s", service_id)
    try:
        response = delete_service(service_id)
        logger.info("Service deleted successfully for Id=%s", response.Id)
        return response
    except ValueError as ex:
        logger.warning("Delete service validation error for Id=%s: %s", service_id, ex)
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except FileNotFoundError as ex:
        logger.warning("Delete service not found for Id=%s: %s", service_id, ex)
        raise HTTPException(status_code=404, detail=str(ex)) from ex

