from pydantic import BaseModel, ConfigDict

class SLOType(str):
    Availability = "Availability"
    Latency = "Latency"
    ErrorRate = "ErrorRate"
    
class SLO(BaseModel):
    ServiceId:str
    API:str
    Type: str
    Description: str
    Target: float
    Unit: str
    Window: str
    Timestamp :str

    model_config = ConfigDict(extra="forbid")