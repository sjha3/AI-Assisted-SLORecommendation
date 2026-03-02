import logging
from uuid import uuid4
from typing import List


from client import write_json_file, update_json_file, read_json_file, delete_json_file
from model.deps_model import Dependency, DepsRequest, DepsResponse

logger = logging.getLogger(__name__)


def create_dependency(dependency_request: DepsRequest) -> DepsResponse:
    dependency_id = str(uuid4())
    logger.info("Creating dependency with generated Id=%s", dependency_id)
    service = Dependency(Id=dependency_id, **dependency_request.model_dump())
    write_json_file(f"{service.Id}.json", service.model_dump(), overwrite=False)
    logger.info("Dependency persisted successfully with Id=%s", service.Id)
    return DepsResponse(Id=dependency_id)


def create_dependencies_batch(dependency_requests: List[DepsRequest]) -> List[DepsResponse]:
    logger.info("Batch dependency create requested for %s items", len(dependency_requests))
    responses: List[DepsResponse] = []

    for dependency_request in dependency_requests:
        responses.append(create_dependency(dependency_request))

    logger.info("Batch dependency create completed. Created %s items", len(responses))
    return responses

def update_dependency(dependency_request: DepsRequest, dependency_id: str) -> DepsResponse:
    logger.info("Updating dependency with Id=%s", dependency_id)
    existing_dependency_data = read_json_file(f"{dependency_id}.json")
    service = Dependency(
        Id=dependency_id,
        ServiceId=existing_dependency_data["ServiceId"],
        API=existing_dependency_data["API"],
        DependsOn=dependency_request.DependsOn
    )
    update_json_file(f"{service.Id}.json", service.model_dump())
    logger.info("Dependency updated successfully with Id=%s", service.Id)
    return DepsResponse(Id=service.Id)

def delete_dependency(dependency_id: str) -> DepsResponse:
    logger.info("Deleting dependency with Id=%s", dependency_id)
    delete_json_file(f"{dependency_id}.json")
    logger.info("Dependency deleted successfully with Id=%s", dependency_id)
    return DepsResponse(Id=dependency_id)