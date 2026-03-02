from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
import csv
import json
import logging
import os, asyncio
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, parse, request

load_dotenv(override=True)

if not logging.getLogger().handlers:
    configured_level = os.getenv("AGENT_LOG_LEVEL", "WARNING").upper()
    logging.basicConfig(
        level=getattr(logging, configured_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

logger = logging.getLogger("agents.data_agent")


def _summarize_tool_output(result: Any) -> str:
    if isinstance(result, list):
        return f"list(len={len(result)})"
    if isinstance(result, dict):
        keys = ",".join(result.keys())
        return f"dict(keys={keys})"
    return type(result).__name__


def _logged_tool(tool_name: str):
    def _decorator(func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            logger.info("tool_call.start tool=%s args=%s kwargs=%s", tool_name, args, kwargs)
            try:
                result = func(*args, **kwargs)
                logger.info(
                    "tool_call.success tool=%s result=%s",
                    tool_name,
                    _summarize_tool_output(result),
                )
                return result
            except Exception as ex:
                logger.exception("tool_call.error tool=%s error=%s", tool_name, ex)
                raise

        return _wrapper

    return _decorator


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value

model_client = AzureOpenAIChatCompletionClient(
    azure_endpoint=_required_env("azure_endpoint"),
    azure_deployment=_required_env("azure_deployment"),
    api_version=_required_env("api_version"),
    api_key=_required_env("api_key"),
    model=_required_env("azure_model_name")
)


def get_impact_graph(service_id: str, api: str) -> Dict[str, Any]:
    """Fetch recommendation payload used for impact context from SLO_Recommend API.

    As requested, this tool performs a GET call to `/slos/recommend`.
    """
    base_url = os.getenv("slo_recommend_api_base", "http://127.0.0.1:8008").rstrip("/")
    query = {"service_id": service_id, "api": api}
    url = f"{base_url}/slos/recommend?{parse.urlencode(query)}"
    logger.debug("tool_call.http tool=get_impact_graph method=GET url=%s", url)

    try:
        with request.urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError):
        logger.warning("tool_call.api_unavailable tool=get_impact_graph")
        return {
            "ServiceId": service_id,
            "API": api,
            "Recommendations": [],
            "SLIComparison": [],
            "LLMExplanation": {
                "Summary": "Unavailable",
                "Explanation": "SLO_Recommend API unavailable",
                "Bottleneck": "Unknown",
            },
        }

    if isinstance(payload, dict):
        return payload
    return {
        "ServiceId": service_id,
        "API": api,
        "Recommendations": [],
        "SLIComparison": [],
        "LLMExplanation": {
            "Summary": "Unexpected response",
            "Explanation": "Expected JSON object from /slos/recommend",
            "Bottleneck": "Unknown",
        },
    }


def get_slo_recommendation(service_id: str, api: str) -> Dict[str, Any]:
    """Fetch SLO recommendation for a service API from SLO_Recommend API."""
    base_url = os.getenv("slo_recommend_api_base", "http://127.0.0.1:8008").rstrip("/")
    query = {"service_id": service_id, "api": api}
    url = f"{base_url}/slos/recommend?{parse.urlencode(query)}"
    logger.debug("tool_call.http tool=get_slo_recommendation method=GET url=%s", url)

    try:
        with request.urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError):
        logger.warning("tool_call.api_unavailable tool=get_slo_recommendation")
        return {
            "ServiceId": service_id,
            "API": api,
            "Recommendations": [],
            "SLIComparison": [],
            "LLMExplanation": {
                "Summary": "Unavailable",
                "Explanation": "SLO_Recommend API unavailable",
                "Bottleneck": "Unknown",
            },
        }

    if isinstance(payload, dict):
        return payload
    return {
        "ServiceId": service_id,
        "API": api,
        "Recommendations": [],
        "SLIComparison": [],
        "LLMExplanation": {
            "Summary": "Unexpected response",
            "Explanation": "Expected JSON object from /slos/recommend",
            "Bottleneck": "Unknown",
        },
    }


def get_impact_analysis(
    service_id: str,
    api: str,
    availability_target: Optional[float] = None,
    latency_target: Optional[float] = None,
    error_rate_target: Optional[float] = None,
) -> Dict[str, Any]:
    """Run impact analysis by calling POST /slos/impact-analysis.

    If no target values are provided, this function first fetches the current
    recommendation from GET /slos/recommend and uses those targets as baseline.
    """
    base_url = os.getenv("slo_recommend_api_base", "http://127.0.0.1:8008").rstrip("/")

    if availability_target is None and latency_target is None and error_rate_target is None:
        recommended = get_slo_recommendation(service_id=service_id, api=api)
        for row in recommended.get("Recommendations", []):
            metric_type = str(row.get("Type", "")).strip().lower()
            target = row.get("Target")
            if target is None:
                continue
            if metric_type == "availability" and availability_target is None:
                availability_target = float(target)
            elif metric_type == "latency" and latency_target is None:
                latency_target = float(target)
            elif metric_type in {"errorrate", "error_rate"} and error_rate_target is None:
                error_rate_target = float(target)

    new_slo: List[Dict[str, Any]] = []
    if availability_target is not None:
        new_slo.append({"Type": "Availability", "Target": float(availability_target), "Unit": "percent"})
    if latency_target is not None:
        new_slo.append({"Type": "Latency", "Target": float(latency_target), "Unit": "p95"})
    if error_rate_target is not None:
        new_slo.append({"Type": "ErrorRate", "Target": float(error_rate_target), "Unit": "percent"})

    if not new_slo:
        return {
            "ServiceId": service_id,
            "API": api,
            "UpstreamChain": [],
            "AffectedNodes": [],
            "LLMImpact": {
                "Summary": "No targets provided",
                "Explanation": "Provide at least one target metric or ensure /slos/recommend returns recommendations.",
                "Bottleneck": "Unknown",
                "Risks": [],
            },
        }

    payload = {
        "ServiceId": service_id,
        "API": api,
        "NewSLO": new_slo,
    }
    body = json.dumps(payload).encode("utf-8")
    url = f"{base_url}/slos/impact-analysis"
    logger.debug("tool_call.http tool=get_impact_analysis method=POST url=%s", url)

    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError):
        logger.warning("tool_call.api_unavailable tool=get_impact_analysis")
        return {
            "ServiceId": service_id,
            "API": api,
            "UpstreamChain": [],
            "AffectedNodes": [],
            "LLMImpact": {
                "Summary": "Unavailable",
                "Explanation": "SLO_Recommend impact API unavailable",
                "Bottleneck": "Unknown",
                "Risks": [],
            },
        }

    if isinstance(parsed, dict):
        return parsed
    return {
        "ServiceId": service_id,
        "API": api,
        "UpstreamChain": [],
        "AffectedNodes": [],
        "LLMImpact": {
            "Summary": "Unexpected response",
            "Explanation": "Expected JSON object from /slos/impact-analysis",
            "Bottleneck": "Unknown",
            "Risks": [],
        },
    }


#get_impact_graph = _logged_tool("get_impact_graph")(get_impact_graph)
#get_slo_recommendation = _logged_tool("get_slo_recommendation")(get_slo_recommendation)

analysis_agent = AssistantAgent(
    name="analysis_agent",
    model_client=model_client,
    tools=[        
        get_impact_analysis,
        get_slo_recommendation,
    ],
    system_message=(
        """
        You are analysis_agent, responsible for peforming analysis on SLI, SLO, Incidents and Service dependencies of a serviec apis. 
        Use folloing tools:
            get_impact_analysis : to perform impact analysis for SLO target changes for services
            get_slo_recommendation : to get SLO recommendations for a service
            
            
        Always return responses in valid JSON format only (no markdown, no prose outside JSON). 
        Return normalized outputs, highlight missing data, and include raw tool results when requested.
        """
        
    ),
)

async def main():
    while True:
        task = input("Enter your query: ")
        logger.info("conversation.start task=%s", task)

        final_result = None
        async for item in analysis_agent.run_stream(task=task):
            content = getattr(item, "content", "")
            if content:
                final_result = content

        if final_result is not None:
            print(final_result)
        else:
            print("No result returned.")

        logger.info("conversation.end")

if __name__ == "__main__":
    asyncio.run(main())