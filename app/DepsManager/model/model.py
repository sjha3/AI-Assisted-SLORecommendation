from typing import List

from pydantic import BaseModel, ConfigDict


class ServiceAPI(BaseModel):
    ServiceId: str
    API: str

    model_config = ConfigDict(extra="forbid")


class DepsRequest(ServiceAPI):
    DependsOn: List[ServiceAPI]

    model_config = ConfigDict(extra="forbid")


class BatchDepsCreateRequest(BaseModel):
    dependencies: List[DepsRequest]

    model_config = ConfigDict(extra="forbid")
