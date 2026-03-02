import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from model.slo_model import (
    AddRecommendedSLORequest,
    AddRecommendedSLOResponse,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    SLORecommendationResponse,
)
from logic import add_recommended_slo_for_service_api, analyze_impact_graph, recommend_slo_with_comparison

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="SLO Recommendation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/slos/recommend", response_model=SLORecommendationResponse)
def recommend_slo(
    service_id: str = Query(...),
    api: str = Query(...),
):
    logger.info("GET /slos/recommend called with service_id=%s api=%s", service_id, api)
    try:
        result = recommend_slo_with_comparison(service_id=service_id, api=api)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex

    #if not result.Recommendations:
    #    raise HTTPException(status_code=404, detail="No SLI found for the given service_id and api")

    return result


@app.post("/slos/impact-analysis", response_model=ImpactAnalysisResponse)
def impact_analysis(payload: ImpactAnalysisRequest):
    logger.info(
        "POST /slos/impact-analysis called with service_id=%s api=%s",
        payload.ServiceId,
        payload.API,
    )
    try:
        result = analyze_impact_graph(
            service_id=payload.ServiceId,
            api=payload.API,
            new_slo=payload.NewSLO,
        )
    except FileNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex

    return result


@app.post("/slos/recommended", response_model=AddRecommendedSLOResponse)
def add_recommended_slo(payload: AddRecommendedSLORequest):
    logger.info(
        "POST /slos/recommended called with service_id=%s api=%s slos=%s",
        payload.ServiceId,
        payload.API,
        len(payload.SLOs),
    )
    try:
        return add_recommended_slo_for_service_api(
            service_id=payload.ServiceId,
            api=payload.API,
            slos=payload.SLOs,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
