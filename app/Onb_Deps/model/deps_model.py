from pydantic import BaseModel, ConfigDict
from typing import List

class ServiceAPI(BaseModel):
    ServiceId: str
    API: str

    model_config = ConfigDict(extra="forbid")
    
class DepsRequest(ServiceAPI):
    DependsOn: list[ServiceAPI]
    model_config = ConfigDict(extra="forbid")


class DepsResponse(BaseModel):
    Id: str

class Dependency(DepsRequest):
    Id: str
    
class BatchDepsCreateRequest(BaseModel):
    dependencies: List[DepsRequest]

    model_config = ConfigDict(extra="forbid")
