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


class SLIComparison(BaseModel):
    Type: str
    SLIValue: float
    RecommendedSLO: float
    Unit: str
    MeetsRecommendation: bool
    Delta: float

    model_config = ConfigDict(extra="forbid")

class LLMExplanation(BaseModel):
    Summary: str
    Explanation: str
    Bottleneck: str

    model_config = ConfigDict(extra="forbid")


class SLORecommendationResponse(BaseModel):
    ServiceId: str
    API: str
    Recommendations: list[SLO]
    SLIComparison: list[SLIComparison]
    LLMExplanation: LLMExplanation

    model_config = ConfigDict(extra="forbid")


class ImpactSLOInput(BaseModel):
    Type: str
    Target: float
    Unit: str

    model_config = ConfigDict(extra="forbid")


class ImpactAnalysisRequest(BaseModel):
    ServiceId: str
    API: str
    NewSLO: list[ImpactSLOInput]

    model_config = ConfigDict(extra="forbid")


class ImpactNodeAnalysis(BaseModel):
    ServiceId: str
    API: str
    CurrentSLO: dict[str, float]
    UpdatedSLO: dict[str, float]
    CurrentSLI: dict[str, float]
    IncidentCount: int

    model_config = ConfigDict(extra="forbid")


class LLMImpactAnalysis(BaseModel):
    Summary: str
    Explanation: str
    Bottleneck: str
    Risks: list[str]

    model_config = ConfigDict(extra="forbid")


class ImpactAnalysisResponse(BaseModel):
    ServiceId: str
    API: str
    UpstreamChain: list[str]
    AffectedNodes: list[ImpactNodeAnalysis]
    LLMImpact: LLMImpactAnalysis

    model_config = ConfigDict(extra="forbid")


class RecommendedSLOInput(BaseModel):
    Type: str
    Target: float
    Unit: str
    Window: str = "28"

    model_config = ConfigDict(extra="forbid")


class AddRecommendedSLORequest(BaseModel):
    ServiceId: str
    API: str
    SLOs: list[RecommendedSLOInput]

    model_config = ConfigDict(extra="forbid")


class AddRecommendedSLOResponse(BaseModel):
    ServiceId: str
    API: str
    FilePath: str
    EntriesCount: int
    SavedAt: str

    model_config = ConfigDict(extra="forbid")