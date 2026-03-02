from pydantic import BaseModel, ConfigDict

class SLIType(str):
    Availability = "Availability"
    Latency = "Latency"
    ErrorRate = "ErrorRate"

class SLI(BaseModel):
    ServiceId:str
    API:str
    Type: str
    Description: str
    Value: float
    Unit: str
    Window: str
    Timestamp :str

    model_config = ConfigDict(extra="forbid")