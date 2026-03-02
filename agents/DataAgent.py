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



def get_slo(service_id: str, api: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch SLO records for a service from the Knowledge_SLO API.

    Use this tool when you need Service Level Objectives (targets) for a service,
    optionally narrowed to a single API.

    Args:
        service_id: Full service resource identifier.
        api: Optional API name/path to filter SLO entries.

    Returns:
        A list of SLO objects. Returns an empty list when no data is available
        or when the SLO API is unreachable.
    """
    base_url = os.getenv("knowledge_slo_api_base", "http://127.0.0.1:8004").rstrip("/")
    query: Dict[str, str] = {"service_id": service_id}
    if api:
        query["api"] = api

    url = f"{base_url}/slos/service?{parse.urlencode(query)}"
    logger.debug("tool_call.http tool=get_slo method=GET url=%s", url)

    try:
        with request.urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError):
        logger.warning("tool_call.api_unavailable tool=get_slo")
        return []

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "value" in payload and isinstance(payload["value"], list):
        return payload["value"]
    return []


def get_sli(service_id: str, api: str, time: str = "latest") -> List[Dict[str, Any]]:
    """Fetch SLI measurements for a service API from the SLI API.

    Use this tool to retrieve observed service indicators such as availability, latency and error for a specific API.

    Args:
        service_id: Full service resource identifier.
        api: API name/path whose SLI values are required.
        time: "latest" for the most recent period, or a positive integer string
            (for example "3") to fetch that many recent months.

    Returns:
        A list of SLI records. Returns an empty list when no data is available
        or when the SLI API is unreachable.
    """
    base_url = os.getenv("sli_api_base", "http://127.0.0.1:8002").rstrip("/")
    query: Dict[str, str] = {"service_id": service_id, "api": api}

    if time.lower() == "latest":
        url = f"{base_url}/slis/latest?{parse.urlencode(query)}"
    elif time.isdigit() and int(time) > 0:
        query["number_of_months"] = str(int(time))
        url = f"{base_url}/slis?{parse.urlencode(query)}"
    else:
        url = f"{base_url}/slis?{parse.urlencode(query)}"

    logger.debug("tool_call.http tool=get_sli method=GET url=%s", url)

    try:
        with request.urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError):
        logger.warning("tool_call.api_unavailable tool=get_sli")
        return []

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "value" in payload and isinstance(payload["value"], list):
        return payload["value"]
    return []


def get_incidents(service_id: str, api: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
    """Fetch incident records for a service API within a time range.

    Use this tool when you need operational incident history affecting an API
    between two timestamps.

    Args:
        service_id: Full service resource identifier.
        api: API name/path to query incidents for.
        start_time: Inclusive start timestamp in ISO-8601 format.
        end_time: Inclusive end timestamp in ISO-8601 format.

    Returns:
        A list of incident objects. Returns an empty list when no matching data
        is available or when the Incidents API is unreachable.
    """
    incidents_api_base = os.getenv("incidents_api_base", "http://127.0.0.1:8005").rstrip("/")
    query = {
        "service_id": service_id,
        "api": api,
        "start_time": start_time,
        "end_time": end_time,
    }
    url = f"{incidents_api_base}/incidents?{parse.urlencode(query)}"
    logger.debug("tool_call.http tool=get_incidents method=GET url=%s", url)

    try:
        with request.urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError):
        logger.warning("tool_call.api_unavailable tool=get_incidents")
        return []

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "value" in payload and isinstance(payload["value"], list):
        return payload["value"]
    return []


def get_dependent_services(service_id: str, api: Optional[str] = None) -> Dict[str, Any]:
    """Fetch  dependencies for a service from the DepsManager API.

    Use this tool to discover which services/APIs the given service depends on.
    When `api` is provided, dependencies are filtered to only that source API.

    Args:
        service_id: Full service resource identifier.
        api: Optional source API name/path to filter dependency edges.

    Returns:
        A normalized dictionary with:
        - service_id: input service identifier
        - api: input API filter (or None)
        - dependencies: list of {service_id, api, via_api}
        - count: total number of returned dependencies
    """
    deps_manager_api_base = os.getenv("deps_manager_api_base", "http://127.0.0.1:8003").rstrip("/")
    url = f"{deps_manager_api_base}/graph/dependencies?{parse.urlencode({'service_id': service_id})}"
    logger.debug("tool_call.http tool=get_dependent_services method=GET url=%s", url)

    try:
        with request.urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError):
        logger.warning("tool_call.api_unavailable tool=get_dependent_services")
        return {"service_id": service_id, "api": api, "dependencies": [], "count": 0}

    depends_on = payload.get("depends_on", []) if isinstance(payload, dict) else []

    deps: List[Dict[str, Any]] = []
    for edge in depends_on:
        from_api = edge.get("from_api")
        if api and from_api != api:
            continue

        deps.append(
            {
                "service_id": edge.get("to_service_id"),
                "api": edge.get("to_api"),
                "via_api": from_api,
            }
        )

    return {
        "service_id": service_id,
        "api": api,
        "dependencies": deps,
        "count": len(deps),
    }


#get_slo = _logged_tool("get_slo")(get_slo)
#get_sli = _logged_tool("get_sli")(get_sli)
#get_incidents = _logged_tool("get_incidents")(get_incidents)
#get_dependent_services = _logged_tool("get_dependent_services")(get_dependent_services)


data_agent = AssistantAgent(
    name="data_agent",
    model_client=model_client,
    tools=[
        get_slo,
        get_sli,
        get_incidents,
        get_dependent_services,
    ],
    system_message=(
        """
        You are data_agent, responsible for gathering SLI, SLO, Incidents and Service dependencies of a serviec api using tools. 
        You can respond to questions related to SLI, Knowledge store SLO, incidents history and dependencies of a service.
        Always prefer tool calls over assumptions.
        Use folloing tools:
            get_slo : to get SLO target from knowledge store, 
            get_sli : to get SLI such as availabilty, latency, error rate for services
            get_incidents: to get incidents for service 
            get_dependent_services: to get dependencies for a service. 
. 
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
        async for item in data_agent.run_stream(task=task):
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