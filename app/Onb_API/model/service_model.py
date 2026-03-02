from pydantic import BaseModel, ConfigDict

class ServiceRequest(BaseModel):
    ServiceId: str
    API: list[str]
    Type: str
    Category: str
    Team: str
    Contact: str

    model_config = ConfigDict(extra="forbid")

class ServiceResponse(BaseModel):
    Id:str

class Service(ServiceRequest):
    Id: str
    