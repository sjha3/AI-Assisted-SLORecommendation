from pydantic import BaseModel, ConfigDict

class IncidentType(str):
    Availability = "Availability"
    Latency = "Latency"
    ErrorRate = "ErrorRate"
    
class Incident(BaseModel):
    ServiceId:str
    API:str
    Id:str
    Type: str
    Severity: str
    Description: str
    Timestamp :str

    model_config = ConfigDict(extra="forbid")