import logging
from uuid import uuid4
from typing import List

try:
    from .client import write_json_file, update_json_file, read_json_file, delete_json_file
    from .model.service_model import Service, ServiceRequest, ServiceResponse
except ImportError:
    from client import write_json_file, update_json_file, read_json_file, delete_json_file
    from model.service_model import Service, ServiceRequest, ServiceResponse

logger = logging.getLogger(__name__)


def create_service(service_request: ServiceRequest) -> ServiceResponse:
    service_id = str(uuid4())
    logger.info("Creating service with generated Id=%s", service_id)
    service = Service(Id=service_id, **service_request.model_dump())
    write_json_file(f"{service.Id}.json", service.model_dump(), overwrite=False)
    logger.info("Service persisted successfully with Id=%s", service.Id)
    return ServiceResponse(Id=service_id)


def create_services_batch(service_requests: List[ServiceRequest]) -> List[ServiceResponse]:
    logger.info("Batch create requested for %s services", len(service_requests))
    responses: List[ServiceResponse] = []

    for service_request in service_requests:
        responses.append(create_service(service_request))

    logger.info("Batch create completed. Created %s services", len(responses))
    return responses

def update_service(service_request: ServiceRequest, service_id: str) -> ServiceResponse:
    logger.info("Updating service with Id=%s", service_id)
    existing_service_data = read_json_file(f"{service_id}.json")
    service = Service(
        Id=service_id,
        ServiceId=existing_service_data["ServiceId"],
        API=existing_service_data["API"],
        Type=service_request.Type,
        Category=service_request.Category,
        Team=service_request.Team,
        Contact=service_request.Contact,
    )
    update_json_file(f"{service.Id}.json", service.model_dump())
    logger.info("Service updated successfully with Id=%s", service_id)
    return ServiceResponse(Id=service_id)

def delete_service(service_id: str) -> ServiceResponse:
    logger.info("Deleting service with Id=%s", service_id)
    delete_json_file(f"{service_id}.json")
    logger.info("Service deleted successfully with Id=%s", service_id)
    return ServiceResponse(Id=service_id)