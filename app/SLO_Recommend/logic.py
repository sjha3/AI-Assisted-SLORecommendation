from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
from openai import AzureOpenAI

try:
    from .client import (
        collect_reachable_nodes,
        get_dependency_graph,
        get_service_category,
        read_sli_rows,
        read_static_slo_rows,
    )
    from .model.slo_model import (
        AddRecommendedSLOResponse,
        ImpactAnalysisResponse,
        ImpactNodeAnalysis,
        ImpactSLOInput,
        LLMExplanation,
        LLMImpactAnalysis,
        RecommendedSLOInput,
        SLO,
        SLIComparison,
        SLORecommendationResponse,
    )
except ImportError:
    from client import (
        collect_reachable_nodes,
        get_dependency_graph,
        get_service_category,
        read_sli_rows,
        read_static_slo_rows,
    )
    from model.slo_model import (
        AddRecommendedSLOResponse,
        ImpactAnalysisResponse,
        ImpactNodeAnalysis,
        ImpactSLOInput,
        LLMExplanation,
        LLMImpactAnalysis,
        RecommendedSLOInput,
        SLO,
        SLIComparison,
        SLORecommendationResponse,
    )


DEFAULT_OVERHEAD_MS = 5.0
AVAILABILITY_BUFFER = 0.1
LATENCY_BUFFER_FACTOR = 1.10
ERROR_RATE_BUFFER_FACTOR = 1.10
logger = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[2]
INCIDENTS_FILE = ROOT_DIR / "DB" / "Incidents" / "incidents.json"
RECOMMENDED_SLO_DIR = ROOT_DIR / "DB" / "RecommendedSLO"


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(str(value))
    except (TypeError, ValueError):
        return default
def _parse_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _default_llm_explanation(summary: str = "LLM explanation unavailable.") -> LLMExplanation:
    return LLMExplanation(
        Summary=summary,
        Explanation="Unable to parse structured LLM explanation.",
        Bottleneck="Unknown",
    )


def _decode_llm_explanation_json(raw_text: str) -> LLMExplanation:
    text = (raw_text or "").strip()
    if not text:
        return _default_llm_explanation()

    def _to_explanation(payload: Dict[str, Any]) -> LLMExplanation:
        return LLMExplanation(
            Summary=str(payload.get("Summary", "")).strip() or "No summary returned.",
            Explanation=str(payload.get("Explanation", "")).strip() or "No explanation returned.",
            Bottleneck=str(payload.get("Bottleneck", "")).strip() or "Unknown",
        )

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return _to_explanation(parsed)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict):
                return _to_explanation(parsed)
        except json.JSONDecodeError:
            pass

    object_match = re.search(r"\{[\s\S]*\}", text)
    if object_match:
        try:
            parsed = json.loads(object_match.group(0))
            if isinstance(parsed, dict):
                return _to_explanation(parsed)
        except json.JSONDecodeError:
            pass

    return LLMExplanation(
        Summary="LLM returned non-JSON content.",
        Explanation=text,
        Bottleneck="Could not decode structured bottleneck.",
    )


def _default_llm_impact(summary: str = "Impact analysis unavailable.") -> LLMImpactAnalysis:
    return LLMImpactAnalysis(
        Summary=summary,
        Explanation="Unable to parse structured impact analysis.",
        Bottleneck="Unknown",
        Risks=[],
    )


def _decode_llm_impact_json(raw_text: str) -> LLMImpactAnalysis:
    text = (raw_text or "").strip()
    if not text:
        return _default_llm_impact()

    def _to_impact(payload: Dict[str, Any]) -> LLMImpactAnalysis:
        risks = payload.get("Risks", [])
        parsed_risks = [str(item).strip() for item in risks if str(item).strip()] if isinstance(risks, list) else []
        return LLMImpactAnalysis(
            Summary=str(payload.get("Summary", "")).strip() or "No summary returned.",
            Explanation=str(payload.get("Explanation", "")).strip() or "No explanation returned.",
            Bottleneck=str(payload.get("Bottleneck", "")).strip() or "Unknown",
            Risks=parsed_risks,
        )

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return _to_impact(parsed)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict):
                return _to_impact(parsed)
        except json.JSONDecodeError:
            pass

    object_match = re.search(r"\{[\s\S]*\}", text)
    if object_match:
        try:
            parsed = json.loads(object_match.group(0))
            if isinstance(parsed, dict):
                return _to_impact(parsed)
        except json.JSONDecodeError:
            pass

    return LLMImpactAnalysis(
        Summary="LLM returned non-JSON content.",
        Explanation=text,
        Bottleneck="Could not decode structured bottleneck.",
        Risks=[],
    )


def _normalize_metric_type(metric_type: str) -> str:
    normalized = metric_type.strip().lower().replace("_", "")
    if normalized == "availability":
        return "Availability"
    if normalized == "latency":
        return "Latency"
    if normalized in {"errorrate", "errors"}:
        return "ErrorRate"
    return metric_type


def _latest_static_slo_by_type(service_id: str, api: str) -> Dict[str, Dict[str, object]]:
    rows = [
        row for row in read_static_slo_rows()
        if row.get("ServiceId") == service_id and row.get("API") == api
    ]
    if not rows:
        return {}

    latest_timestamp = max(_parse_timestamp(str(row.get("Timestamp", ""))) for row in rows)
    latest_rows = [row for row in rows if _parse_timestamp(str(row.get("Timestamp", ""))) == latest_timestamp]
    by_type: Dict[str, Dict[str, object]] = {}
    for row in latest_rows:
        metric_type = _normalize_metric_type(str(row.get("Type", "")))
        if metric_type and metric_type not in by_type:
            by_type[metric_type] = row
    return by_type


def _latest_sli_metrics_for_node(service_id: str, api: str) -> Dict[str, float]:
    sli_by_type = _latest_sli_by_type(service_id, api)
    availability = _to_float(sli_by_type.get("Availability", {}).get("Value", 0.0), default=0.0)
    latency = _to_float(sli_by_type.get("Latency", {}).get("Value", 0.0), default=0.0)
    error_rate = _to_float(sli_by_type.get("ErrorRate", {}).get("Value", 0.0), default=0.0)
    if "ErrorRate" not in sli_by_type and availability > 0:
        error_rate = _derive_error_rate_from_availability(availability)
    return {
        "Availability": round(availability, 4),
        "Latency": round(latency, 4),
        "ErrorRate": round(error_rate, 4),
    }


def _current_slo_with_sli_buffer(service_id: str, api: str) -> Dict[str, float]:
    static_by_type = _latest_static_slo_by_type(service_id, api)
    sli_metrics = _latest_sli_metrics_for_node(service_id, api)

    availability = _to_float(static_by_type.get("Availability", {}).get("Target", 0.0), default=0.0)
    latency = _to_float(static_by_type.get("Latency", {}).get("Target", 0.0), default=0.0)
    error_rate = _to_float(static_by_type.get("ErrorRate", {}).get("Target", 0.0), default=0.0)

    used_sli_fallback = False
    if availability <= 0 and sli_metrics["Availability"] > 0:
        availability = max(0.0, sli_metrics["Availability"] - AVAILABILITY_BUFFER)
        used_sli_fallback = True
    if latency <= 0 and sli_metrics["Latency"] > 0:
        latency = sli_metrics["Latency"] * LATENCY_BUFFER_FACTOR
        used_sli_fallback = True
    if error_rate <= 0:
        if sli_metrics["ErrorRate"] > 0:
            error_rate = sli_metrics["ErrorRate"] * ERROR_RATE_BUFFER_FACTOR
            used_sli_fallback = True
        elif availability > 0:
            error_rate = _derive_error_rate_from_availability(availability)
            used_sli_fallback = True

    if availability <= 0:
        availability = 99.0
    if latency <= 0:
        latency = 200.0
    if error_rate <= 0:
        error_rate = 1.0

    resolved = {
        "Availability": round(availability, 4),
        "Latency": round(latency, 4),
        "ErrorRate": round(error_rate, 4),
    }
    logger.info(
        "Resolved current SLO for %s/%s (used_sli_fallback=%s): %s",
        service_id,
        api,
        used_sli_fallback,
        resolved,
    )
    return resolved


def _build_reverse_graph(graph: Dict[Tuple[str, str], List[Tuple[str, str]]]) -> Dict[Tuple[str, str], List[Tuple[str, str]]]:
    reverse: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    for source, dependencies in graph.items():
        reverse.setdefault(source, [])
        for dep in dependencies:
            reverse.setdefault(dep, [])
            reverse[dep].append(source)
    logger.info("Built reverse dependency graph with node_count=%s", len(reverse))
    return reverse


def _collect_upstream_nodes(
    target: Tuple[str, str],
    reverse_graph: Dict[Tuple[str, str], List[Tuple[str, str]]],
) -> List[Tuple[str, str]]:
    visited: Set[Tuple[str, str]] = set()
    queue: List[Tuple[str, str]] = [target]
    distances: Dict[Tuple[str, str], int] = {target: 0}

    while queue:
        node = queue.pop(0)
        for upstream in reverse_graph.get(node, []):
            if upstream not in distances:
                distances[upstream] = distances[node] + 1
                queue.append(upstream)
            visited.add(upstream)

    ordered = sorted(visited, key=lambda node: distances.get(node, 999999))
    logger.info(
        "Collected upstream chain for %s/%s: count=%s nodes=%s",
        target[0],
        target[1],
        len(ordered),
        ordered,
    )
    return ordered


def _recompute_node_slo_from_dependencies(
    node: Tuple[str, str],
    graph: Dict[Tuple[str, str], List[Tuple[str, str]]],
    metrics_map: Dict[Tuple[str, str], Dict[str, float]],
) -> Dict[str, float]:
    dependencies = graph.get(node, [])
    if not dependencies:
        logger.info("No dependencies for node %s/%s; using existing current/fallback SLO", node[0], node[1])
        return metrics_map.get(node, _current_slo_with_sli_buffer(node[0], node[1]))

    dep_metrics = [metrics_map.get(dep) for dep in dependencies]
    logger.info("Recomputing SLO for node %s/%s based on dependencies %s with metrics %s", node[0], node[1], dependencies, dep_metrics)
    if any(metric is None for metric in dep_metrics):
        logger.warning("Missing dependency metrics for node %s/%s; using existing current/fallback SLO", node[0], node[1])
        return metrics_map.get(node, _current_slo_with_sli_buffer(node[0], node[1]))

    availability = 1.0
    for metric in dep_metrics:
        availability *= metric["Availability"] / 100.0
    availability *= 100.0

    latency = sum(metric["Latency"] for metric in dep_metrics) + DEFAULT_OVERHEAD_MS

    reliability = 1.0
    for metric in dep_metrics:
        dep_error_fraction = max(0.0, min(1.0, metric["ErrorRate"] / 100.0))
        reliability *= (1.0 - dep_error_fraction)
    error_rate = (1.0 - reliability) * 100.0
    logger.info("Recomputed SLO for node %s/%s from dependencies: Availability=%.4f%% Latency=%.4fms ErrorRate=%.4f%%", node[0], node[1], availability, latency, error_rate)
    return {
        "Availability": round(max(0.0, min(100.0, availability)), 4),
        "Latency": round(max(0.0, latency), 4),
        "ErrorRate": round(max(0.0, min(100.0, error_rate)), 4),
    }


def _topological_postorder(
    root: Tuple[str, str],
    graph: Dict[Tuple[str, str], List[Tuple[str, str]]],
    reachable: Set[Tuple[str, str]],
) -> List[Tuple[str, str]]:
    order: List[Tuple[str, str]] = []
    state: Dict[Tuple[str, str], int] = {}

    def dfs(node: Tuple[str, str]) -> None:
        current_state = state.get(node, 0)
        if current_state == 2:
            return
        if current_state == 1:
            return

        state[node] = 1
        for dep in graph.get(node, []):
            if dep in reachable:
                dfs(dep)
        state[node] = 2
        order.append(node)

    dfs(root)
    logger.info("Topological postorder result for root %s/%s: %s", root[0], root[1], order)
    return order


def _latest_sli_by_type(service_id: str, api: str) -> Dict[str, Dict[str, str]]:
    rows = [
        row for row in read_sli_rows()
        if row.get("ServiceId") == service_id and row.get("API") == api
    ]
    if not rows:
        logger.debug("No SLI rows found for service_id=%s api=%s", service_id, api)
        return {}

    latest_timestamp = max(_parse_timestamp(row["Timestamp"]) for row in rows)
    latest_rows = [row for row in rows if _parse_timestamp(row["Timestamp"]) == latest_timestamp]

    by_type: Dict[str, Dict[str, str]] = {}
    for row in latest_rows:
        slo_type = row.get("Type", "")
        if slo_type and slo_type not in by_type:
            by_type[slo_type] = row

    logger.debug("Latest SLI types for service_id=%s api=%s: %s", service_id, api, list(by_type.keys()))
    return by_type


def _external_static_slo_by_type(service_id: str, api: str) -> Dict[str, Dict[str, object]]:
    rows = [
        row for row in read_static_slo_rows()
        if row.get("ServiceId") == service_id and row.get("API") == api
    ]
    if not rows:
        logger.info("No static external SLO rows found for service_id=%s api=%s", service_id, api)
        return {}

    latest_timestamp = max(_parse_timestamp(str(row.get("Timestamp", ""))) for row in rows)
    latest_rows = [row for row in rows if _parse_timestamp(str(row.get("Timestamp", ""))) == latest_timestamp]

    by_type: Dict[str, Dict[str, object]] = {}
    logger.info("===========%s ", latest_rows)
    for row in latest_rows:
        slo_type = str(row.get("Type", ""))
        if slo_type and slo_type not in by_type:
            by_type[slo_type] = row

    logger.info("Static SLO types for service_id=%s api=%s: %s", service_id, api, list(by_type.keys()))
    return by_type


def _derive_error_rate_from_availability(availability_percent: float) -> float:
    return round(max(0.0, 100.0 - availability_percent), 4)


def _metrics_from_external_or_sli(service_id: str, api: str) -> Optional[Dict[str, float]]:
    static_by_type = _external_static_slo_by_type(service_id, api)
    sli_by_type = _latest_sli_by_type(service_id, api)

    availability = None
    latency = None
    error_rate = None

    availability_row = static_by_type.get("Availability")
    logger.info("%s ", static_by_type)
    if availability_row is not None:
        availability = _to_float(availability_row.get("Target", 0), default=0.0)
    elif "Availability" in sli_by_type:
        availability = _to_float(sli_by_type["Availability"].get("Value", "0") or 0, default=0.0)

    latency_row = static_by_type.get("Latency")
    logger.info("%s ", latency_row)
    if latency_row is not None:
        latency = _to_float(latency_row.get("Target", 0), default=0.0)
    elif "Latency" in sli_by_type:
        latency = _to_float(sli_by_type["Latency"].get("Value", "0") or 0, default=0.0)

    error_rate_row = static_by_type.get("ErrorRate")
    if error_rate_row is not None:
        error_rate = _to_float(error_rate_row.get("Target", 0), default=0.0)
    elif "ErrorRate" in sli_by_type:
        error_rate = _to_float(sli_by_type["ErrorRate"].get("Value", "0") or 0, default=0.0)
    elif availability is not None:
        error_rate = _derive_error_rate_from_availability(availability)

    if availability is None and latency is None and error_rate is None:
        return None
    logger.info("Returning external computed SLO recommendation for service_id=%s api=%s latency = %s, availability = %s, error_rate = %s", service_id, api, latency, availability, error_rate)

    return {
        "availability": availability if availability is not None else 99.0,
        "latency": latency if latency is not None else 0.0,
        "error_rate": error_rate if error_rate is not None else 1.0,
    }


def _base_internal_metrics(service_id: str, api: str) -> Optional[Dict[str, float]]:
    sli_by_type = _latest_sli_by_type(service_id, api)
    if not sli_by_type:
        return None

    availability = _to_float(sli_by_type.get("Availability", {}).get("Value", "0") or 0, default=0.0)
    latency = _to_float(sli_by_type.get("Latency", {}).get("Value", "0") or 0, default=0.0)
    error_rate = _to_float(sli_by_type.get("ErrorRate", {}).get("Value", "0") or 0, default=0.0)

    if "ErrorRate" not in sli_by_type:
        error_rate = _derive_error_rate_from_availability(availability)
    logger.info("Returning internal computed SLO recommendation for service_id=%s api=%s availability = %s, latency = %s, error_rate = %s", service_id, api, availability, latency, error_rate)
    return {
        "availability": availability,
        "latency": latency,
        "error_rate": error_rate,
    }


def _compute_recommended_metrics_by_node(
    service_id: str,
    api: str,
) -> Tuple[Optional[Dict[str, float]], Dict[Tuple[str, str], Dict[str, float]], List[Tuple[str, str]]]:
    category = (get_service_category(service_id, api) or "Internal").lower()

    if category == "external":
        external_metrics = _metrics_from_external_or_sli(service_id, api)
        if not external_metrics:
            return None, {}, []
        return external_metrics, {(service_id, api): external_metrics}, []

    root = (service_id, api)
    graph = get_dependency_graph()
    reachable = collect_reachable_nodes(root, graph)
    topo_order = _topological_postorder(root, graph, reachable)

    metrics_by_node: Dict[Tuple[str, str], Dict[str, float]] = {}

    for node in topo_order:
        node_service, node_api = node
        node_category = (get_service_category(node_service, node_api) or "Internal").lower()
        logger.info("Evaluating node service_id=%s api=%s category=%s", node_service, node_api, node_category)

        if node_category == "external":
            external_metrics = _metrics_from_external_or_sli(node_service, node_api)
            if not external_metrics:
                logger.info("Missing external metrics for node service_id=%s api=%s", node_service, node_api)
                return None, {}, []
            metrics_by_node[node] = external_metrics
            continue

        dependencies = [dep for dep in graph.get(node, []) if dep in reachable]
        if not dependencies:
            base_metrics = _base_internal_metrics(node_service, node_api)
            if not base_metrics:
                base_metrics = _metrics_from_external_or_sli(node_service, node_api)
            if not base_metrics:
                logger.warning("Missing base metrics for leaf node service_id=%s api=%s", node_service, node_api)
                return None, {}, []
            metrics_by_node[node] = base_metrics
            continue

        dep_metrics = [metrics_by_node[dep] for dep in dependencies if dep in metrics_by_node]
        if len(dep_metrics) != len(dependencies):
            logger.warning("Dependency metrics missing for node service_id=%s api=%s", node_service, node_api)
            return None, {}, []

        availability = 1.0
        for dep in dep_metrics:
            availability *= dep["availability"] / 100.0
        availability *= 100.0

        latency = sum(dep["latency"] for dep in dep_metrics) + DEFAULT_OVERHEAD_MS

        reliability = 1.0
        for dep in dep_metrics:
            dep_error_fraction = max(0.0, min(1.0, dep["error_rate"] / 100.0))
            reliability *= (1.0 - dep_error_fraction)
        error_rate = (1.0 - reliability) * 100.0

        metrics_by_node[node] = {
            "availability": round(max(0.0, min(100.0, availability)), 4),
            "latency": round(max(0.0, latency), 4),
            "error_rate": round(max(0.0, min(100.0, error_rate)), 4),
        }
        logger.info(
            "Computed node metrics service_id=%s api=%s availability=%s latency=%s error_rate=%s",
            node_service,
            node_api,
            metrics_by_node[node]["availability"],
            metrics_by_node[node]["latency"],
            metrics_by_node[node]["error_rate"],
        )

    final_metrics = metrics_by_node.get(root)
    return final_metrics, metrics_by_node, topo_order


def get_dependency_slo_recommendations(service_id: str, api: str) -> List[SLO]:
    root = (service_id, api)
    final_metrics, metrics_by_node, topo_order = _compute_recommended_metrics_by_node(service_id, api)
    if not final_metrics or not metrics_by_node:
        return []

    dependency_slos: List[SLO] = []
    for node in topo_order:
        if node == root:
            continue
        node_metrics = metrics_by_node.get(node)
        if not node_metrics:
            continue
        dependency_slos.extend(_to_slo_rows(node[0], node[1], node_metrics, source="dependency-computed"))

    logger.info(
        "Prepared dependency SLO rows for service_id=%s api=%s count=%s",
        service_id,
        api,
        len(dependency_slos),
    )
    return dependency_slos


def recommend_slo_for_service_api(service_id: str, api: str) -> List[SLO]:
    logger.info("Recommend SLO called for service_id=%s api=%s", service_id, api)
    category = (get_service_category(service_id, api) or "Internal").lower()
    logger.info("Resolved input service category=%s for service_id=%s api=%s", category, service_id, api)

    if category == "external":
        external_metrics = _metrics_from_external_or_sli(service_id, api)
        if not external_metrics:
            logger.warning("No metrics found for external service_id=%s api=%s", service_id, api)
            return []
        logger.info("Returning external SLO recommendation for service_id=%s api=%s", service_id, api)
        return _to_slo_rows(service_id, api, external_metrics, source="external")

    final_metrics, _, topo_order = _compute_recommended_metrics_by_node(service_id, api)
    if not final_metrics:
        logger.warning(
            "Final metrics not found from dependency computation for service_id=%s api=%s; trying root metric fallback",
            service_id,
            api,
        )
        fallback_metrics = _base_internal_metrics(service_id, api) or _metrics_from_external_or_sli(service_id, api)
        if not fallback_metrics:
            logger.warning("No fallback metrics found for service_id=%s api=%s", service_id, api)
            return []
        logger.info("Returning fallback SLO recommendation for service_id=%s api=%s", service_id, api)
        return _to_slo_rows(service_id, api, fallback_metrics, source="root-fallback")
    logger.info("Topological order size for root %s/%s: %s", service_id, api, len(topo_order))

    logger.info(
        "Final recommendation computed for service_id=%s api=%s availability=%s latency=%s error_rate=%s",
        service_id,
        api,
        final_metrics["availability"],
        final_metrics["latency"],
        final_metrics["error_rate"],
    )
    logger.info("Returning computed SLO recommendation for service_id=%s api=%s", service_id, api)
    return _to_slo_rows(service_id, api, final_metrics, source="computed")


def _is_sli_meeting_slo(slo_type: str, sli_value: float, slo_target: float) -> bool:
    normalized = slo_type.lower()
    if normalized in {"latency", "errorrate", "error_rate"}:
        return sli_value <= slo_target
    return sli_value >= slo_target


def get_sli_comparison_for_service_api(service_id: str, api: str, recommendations: List[SLO]) -> List[SLIComparison]:
    latest_sli_by_type = _latest_sli_by_type(service_id, api)
    comparisons: List[SLIComparison] = []

    for recommendation in recommendations:
        sli_row = latest_sli_by_type.get(recommendation.Type, {})
        sli_value = _to_float(sli_row.get("Value", 0.0), default=0.0)

        meets = _is_sli_meeting_slo(recommendation.Type, sli_value, recommendation.Target)
        delta = round(sli_value - recommendation.Target, 4)

        comparisons.append(
            SLIComparison(
                Type=recommendation.Type,
                SLIValue=round(sli_value, 4),
                RecommendedSLO=round(recommendation.Target, 4),
                Unit=recommendation.Unit,
                MeetsRecommendation=meets,
                Delta=delta,
            )
        )

    logger.info(
        "Built SLI comparison for service_id=%s api=%s metrics=%s",
        service_id,
        api,
        len(comparisons),
    )
    return comparisons


def recommend_slo_with_comparison(service_id: str, api: str) -> SLORecommendationResponse:
    recommendations = recommend_slo_for_service_api(service_id, api)
    comparisons = get_sli_comparison_for_service_api(service_id, api, recommendations)
    incidents = get_incidents_for_service_api(service_id, api)
    dependency_slos = get_dependency_slo_recommendations(service_id, api)
    logger.info("Calling LLM for %s with %s recommendations", service_id, recommendations)
    explanation = _default_llm_explanation()
    try:
        explanation = explain_recommended_slo_with_llm(
            service_id=service_id,
            api=api,
            recommendations=recommendations,
            sli_comparison=comparisons,
            incidents=incidents,
            dependency_slos=dependency_slos,
        )
    except Exception as ex:
        logger.warning(
            "Failed to generate LLM explanation for service_id=%s api=%s: %s",
            service_id,
            api,
            ex,
        )
    logger.info("Returning final SLO recommendation response for service_id=%s api=%s", service_id, api)
    return SLORecommendationResponse(
        ServiceId=service_id,
        API=api,
        Recommendations=recommendations,
        SLIComparison=comparisons,
        LLMExplanation=explanation,
    )


def get_incidents_for_service_api(service_id: str, api: str, limit: int = 20) -> List[Dict[str, str]]:
    if not INCIDENTS_FILE.exists():
        logger.warning("Incidents file not found: %s", INCIDENTS_FILE)
        return []

    with INCIDENTS_FILE.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    incidents = payload.get("incidents", []) if isinstance(payload, dict) else []
    filtered = [
        incident for incident in incidents
        if isinstance(incident, dict)
        and incident.get("ServiceId") == service_id
        and incident.get("API") == api
    ]

    filtered.sort(
        key=lambda incident: _parse_timestamp(str(incident.get("Timestamp", "1970-01-01T00:00:00Z"))),
        reverse=True,
    )

    if limit > 0:
        filtered = filtered[:limit]

    logger.info("Fetched incidents for service_id=%s api=%s count=%s",service_id,api,len(filtered))
    return [dict(incident) for incident in filtered]


def explain_recommended_slo_with_llm(
    service_id: str,
    api: str,
    recommendations: List[SLO],
    sli_comparison: List[SLIComparison],
    incidents: Optional[List[Dict[str, str]]] = None,
    dependency_slos: Optional[List[SLO]] = None,
) -> LLMExplanation:
    load_dotenv(ROOT_DIR / ".env")

    azure_endpoint = os.getenv("azure_endpoint")
    azure_deployment = os.getenv("azure_deployment")
    api_version = os.getenv("api_version")
    api_key = os.getenv("api_key")
    azure_model_name = os.getenv("azure_model_name")

    missing = [
        name for name, value in [
            ("azure_endpoint", azure_endpoint),
            ("azure_deployment", azure_deployment),
            ("api_version", api_version),
            ("api_key", api_key),
            ("azure_model_name", azure_model_name),
        ]
        if not value
    ]
    if missing:
        raise ValueError(f"Missing Azure LLM environment settings: {', '.join(missing)}")

    incidents_payload = incidents if incidents is not None else get_incidents_for_service_api(service_id, api)
    dependency_slo_payload: List[Dict[str, Any]] = [
        item.model_dump() for item in (dependency_slos or get_dependency_slo_recommendations(service_id, api))
    ]

    recommendation_payload: List[Dict[str, Any]] = [item.model_dump() for item in recommendations]
    comparison_payload: List[Dict[str, Any]] = [item.model_dump() for item in sli_comparison]
    '''
    system_prompt = (
        """
        You are an SRE assistant. Explain recommended SLO targets using observed SLI and incident history of service.
        Use dependency SLO as well for analysis of recommendation 
        Be concise, practical, and include key tradeoffs.
        """
    )
    '''
    system_prompt = (
        """
        You are a Senior Site Reliability Engineer (SRE) specializing in distributed system observability and performance optimization. 
        You receive input as a target service, dependency graph and result of deterministic SLO calculation.
        Your job is to analyse this data, correlate the service SLOs with dependencies, provide a clear justification for it and identify bottlenecks if any in the system.
        You must follow these rules:
            - Use only the data provided.
            - Do not invent SLO/SLI values yourself.
            - You will receive input in following JSON format.
        
        Recommend SLO of Current Service: {Availability : %, p95Latency : Y ms, Error Rate : Y%}
        Focus on reasoning, don’t try to recalculate SLOs
        For the target service
        -	Understand Dependency Chain and their SLOs
        -	Analyze SLOs of dependency Chain and include that in your analysis and justification of recommended SLO
        -	Analyze SLO Recommendation based on calculated SLO and dependencies SLOs
        -	Explain how their SLOs combine to influence SLO of target service
        -	Explain how calculated SLO compare with SLIs of service and justfify recommended SLO based on SLI, Incidents and Calculated SLO.
        -	Identify potential bottlenecks and pinpoint the dependencies which are causing highest risk.
        Include Information of Dependency service and their SLOs in reposnse
        Return ONLY a valid JSON object (no markdown) with exactly these keys:
            Summary: string, (Summarize your finding)
            DependencyAndConstraints: string, (Analysis of dependencies, their SLOs and comparison with SLO of current service)
            Explanation: string,  (Explanation of slo recommended)
            Bottleneck: string, (Any bottleneck in the system)
            Risks: string (Any risk in the system)
        }
        
        """
    )
    user_prompt = (
        f"ServiceId: {service_id}\n"
        f"API: {api}\n"
        f"AzureModelName: {azure_model_name}\n"
        f"RecommendedSLO: {json.dumps(recommendation_payload, ensure_ascii=False)}\n"
        f"DependencySLO: {json.dumps(dependency_slo_payload, ensure_ascii=False)}\n"
        f"SLIComparison: {json.dumps(comparison_payload, ensure_ascii=False)}\n"
        f"Incidents: {json.dumps(incidents_payload, ensure_ascii=False)}\n\n"
    )

    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
    )
    response = client.chat.completions.create(
        model=azure_deployment,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    message = response.choices[0].message.content if response.choices else ""
    explanation = _decode_llm_explanation_json(message or "")
    logger.info("Generated SLO explanation using Azure LLM for service_id=%s api=%s explanation=%s", service_id, api, explanation)
    return explanation


def get_recommended_slo_explanation(service_id: str, api: str) -> LLMExplanation:
    recommendations = recommend_slo_for_service_api(service_id, api)
    comparisons = get_sli_comparison_for_service_api(service_id, api, recommendations)
    incidents = get_incidents_for_service_api(service_id, api)
    dependency_slos = get_dependency_slo_recommendations(service_id, api)
    return explain_recommended_slo_with_llm(
        service_id=service_id,
        api=api,
        recommendations=recommendations,
        sli_comparison=comparisons,
        incidents=incidents,
        dependency_slos=dependency_slos,
    )


def _new_slo_to_metric_map(new_slo: List[ImpactSLOInput]) -> Dict[str, float]:
    metric_map: Dict[str, float] = {}
    for item in new_slo:
        metric_type = _normalize_metric_type(item.Type)
        if metric_type in {"Availability", "Latency", "ErrorRate"}:
            metric_map[metric_type] = float(item.Target)
    logger.info("Normalized input new_slo to metric updates: %s", metric_map)
    return metric_map


def explain_impact_with_llm(
    service_id: str,
    api: str,
    new_slo: List[ImpactSLOInput],
    upstream_chain: List[str],
    affected_nodes: List[ImpactNodeAnalysis],
    impact_context: List[Dict[str, Any]],
) -> LLMImpactAnalysis:
    logger.info(
        "Preparing LLM impact analysis payload for %s/%s (upstream_count=%s affected_nodes=%s)",
        service_id,
        api,
        len(upstream_chain),
        len(affected_nodes),
    )
    load_dotenv(ROOT_DIR / ".env")

    azure_endpoint = os.getenv("azure_endpoint")
    azure_deployment = os.getenv("azure_deployment")
    api_version = os.getenv("api_version")
    api_key = os.getenv("api_key")
    azure_model_name = os.getenv("azure_model_name")

    missing = [
        name for name, value in [
            ("azure_endpoint", azure_endpoint),
            ("azure_deployment", azure_deployment),
            ("api_version", api_version),
            ("api_key", api_key),
            ("azure_model_name", azure_model_name),
        ]
        if not value
    ]
    if missing:
        raise ValueError(f"Missing Azure LLM environment settings: {', '.join(missing)}")

    system_prompt = (
        "You are an SRE impact analysis assistant. Analyze upstream impact from an SLO change and call out risks. "
        "Use current SLO, updated SLO, SLI, and incidents to justify conclusions."
        """
        You are a Senior Site Reliability Engineer (SRE) specializing in distributed system observability and performance optimization. 
        Your job is to Analyze upstream impact from an SLO change and call out risks.
        You must follow these rules:
            - Use only the data provided.
            - Do not invent SLO/SLI values yourself.
            - You will receive input in following JSON format.
        
        Recommend SLO of Current Service: {Availability : %, p95Latency : Y ms, Error Rate : Y%}
        Focus on reasoning, don’t try to recalculate SLOs
        For the target service
        -	Understand Dependency Chain of Upstream Services and their SLOs
        -	Analyze change in SLO of current services, change in SLOs of dependency Chain and include that in your analysis
        -	Explain how change in SLO of current service is impacting change in SLOs of target service
        -	Explain how calculated SLO compare with SLIs of service. Use new SLO, SLI, Incidents for analysis.
        Include Information of Dependency service and their SLOs in reposnse
        Return ONLY a valid JSON object (no markdown) with exactly these keys:
            Summary: string, (Summarize your finding)
            Explanation: string,  (Explanation of your finding recommended)
            Bottleneck: string, (Any bottleneck in the system)
            Risks: string (Any risk in the system)
        """
    )
    user_prompt = (
        f"ServiceId: {service_id}\n"
        f"API: {api}\n"
        f"AzureModelName: {azure_model_name}\n"
        f"NewSLO: {json.dumps([item.model_dump() for item in new_slo], ensure_ascii=False)}\n"
        f"UpstreamChain: {json.dumps(upstream_chain, ensure_ascii=False)}\n"
        f"AffectedNodes: {json.dumps([item.model_dump() for item in affected_nodes], ensure_ascii=False)}\n"
        f"ImpactContext: {json.dumps(impact_context, ensure_ascii=False)}\n\n"
        "Return ONLY a valid JSON object with exactly these keys:\n"
        "{\"Summary\": string, \"Explanation\": string, \"Bottleneck\": string, \"Risks\": string[]}\n"
        "Risks must contain concise actionable risk points."
    )

    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
    )
    response = client.chat.completions.create(
        model=azure_deployment,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    logger.info("System prompt : %s", system_prompt)
    logger.info("User prompt: %s", user_prompt)
    message = response.choices[0].message.content if response.choices else ""
    logger.info("Received LLM impact response (chars=%s)", len(message or ""))
    return _decode_llm_impact_json(message or "")


def analyze_impact_graph(service_id: str, api: str, new_slo: List[ImpactSLOInput]) -> ImpactAnalysisResponse:
    logger.info("Starting impact analysis workflow for service_id=%s api=%s", service_id, api)
    target = (service_id, api)
    graph = get_dependency_graph()
    logger.info("Loaded dependency graph for impact analysis with root_candidates=%s", len(graph))
    reverse_graph = _build_reverse_graph(graph)
    upstream_nodes = _collect_upstream_nodes(target, reverse_graph)

    all_nodes: Set[Tuple[str, str]] = set(graph.keys())
    for dependencies in graph.values():
        all_nodes.update(dependencies)
    all_nodes.add(target)

    current_metrics_map: Dict[Tuple[str, str], Dict[str, float]] = {
        node: _current_slo_with_sli_buffer(node[0], node[1]) for node in all_nodes
    }
    logger.info("Prepared current metrics map for node_count=%s", len(current_metrics_map))
    updated_metrics_map: Dict[Tuple[str, str], Dict[str, float]] = {
        node: dict(metrics) for node, metrics in current_metrics_map.items()
    }

    metric_updates = _new_slo_to_metric_map(new_slo)
    target_metrics = dict(updated_metrics_map.get(target, _current_slo_with_sli_buffer(service_id, api)))
    logger.info("Current target metrics before override for %s/%s: %s", service_id, api, target_metrics)
    target_metrics.update(metric_updates)
    updated_metrics_map[target] = target_metrics
    logger.info("Target metrics after applying new_slo for %s/%s: %s", service_id, api, target_metrics)

    for node in upstream_nodes:
        updated_metrics_map[node] = _recompute_node_slo_from_dependencies(node, graph, updated_metrics_map)
    logger.info("Completed upstream recomputation for upstream_count=%s", len(upstream_nodes))

    affected_nodes: List[ImpactNodeAnalysis] = []
    impact_context: List[Dict[str, Any]] = []
    for node in upstream_nodes:
        current_sli = _latest_sli_metrics_for_node(node[0], node[1])
        incidents = get_incidents_for_service_api(node[0], node[1], limit=20)

        affected_nodes.append(
            ImpactNodeAnalysis(
                ServiceId=node[0],
                API=node[1],
                CurrentSLO=current_metrics_map[node],
                UpdatedSLO=updated_metrics_map[node],
                CurrentSLI=current_sli,
                IncidentCount=len(incidents),
            )
        )
        impact_context.append(
            {
                "ServiceId": node[0],
                "API": node[1],
                "CurrentSLO": current_metrics_map[node],
                "UpdatedSLO": updated_metrics_map[node],
                "CurrentSLI": current_sli,
                "Incidents": incidents,
            }
        )
    logger.info("Built impact context entries=%s", len(impact_context))

    llm_impact = _default_llm_impact()
    try:
        logger.info("Invoking LLM impact explanation for service_id=%s api=%s", service_id, api)
        llm_impact = explain_impact_with_llm(
            service_id=service_id,
            api=api,
            new_slo=new_slo,
            upstream_chain=[f"{node[0]}::{node[1]}" for node in upstream_nodes],
            affected_nodes=affected_nodes,
            impact_context=impact_context,
        )
    except Exception as ex:
        logger.warning(
            "Failed to generate impact analysis for service_id=%s api=%s: %s",
            service_id,
            api,
            ex,
        )

    logger.info(
        "Completed impact analysis workflow for %s/%s (upstream_count=%s, risks=%s)",
        service_id,
        api,
        len(upstream_nodes),
        len(llm_impact.Risks),
    )

    return ImpactAnalysisResponse(
        ServiceId=service_id,
        API=api,
        UpstreamChain=[f"{node[0]}::{node[1]}" for node in upstream_nodes],
        AffectedNodes=affected_nodes,
        LLMImpact=llm_impact,
    )


def _recommended_slo_filename(service_id: str, api: str) -> str:
    safe_service = re.sub(r"[^A-Za-z0-9._-]", "_", service_id.strip())
    safe_api = re.sub(r"[^A-Za-z0-9._-]", "_", api.strip())
    return f"{safe_service}__{safe_api}.json"


def add_recommended_slo_for_service_api(
    service_id: str,
    api: str,
    slos: List[RecommendedSLOInput],
) -> AddRecommendedSLOResponse:
    if not service_id.strip() or not api.strip():
        raise ValueError("ServiceId and API are required")
    if not slos:
        raise ValueError("At least one SLO entry is required")

    RECOMMENDED_SLO_DIR.mkdir(parents=True, exist_ok=True)
    file_path = RECOMMENDED_SLO_DIR / _recommended_slo_filename(service_id, api)
    saved_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    existing_entries: List[Dict[str, Any]] = []
    if file_path.exists():
        try:
            with file_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            existing_entries = payload.get("entries", []) if isinstance(payload, dict) else []
            if not isinstance(existing_entries, list):
                existing_entries = []
        except (json.JSONDecodeError, OSError):
            existing_entries = []

    new_entry = {
        "SavedAt": saved_at,
        "SLOs": [item.model_dump() for item in slos],
    }
    existing_entries.append(new_entry)

    output = {
        "ServiceId": service_id,
        "API": api,
        "entries": existing_entries,
    }
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    logger.info(
        "Persisted recommended SLO for service_id=%s api=%s at %s (entries=%s)",
        service_id,
        api,
        file_path,
        len(existing_entries),
    )
    return AddRecommendedSLOResponse(
        ServiceId=service_id,
        API=api,
        FilePath=str(file_path),
        EntriesCount=len(existing_entries),
        SavedAt=saved_at,
    )


def _to_slo_rows(service_id: str, api: str, metrics: Dict[str, float], source: str) -> List[SLO]:
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return [
        SLO(
            ServiceId=service_id,
            API=api,
            Type="Availability",
            Description=f"Recommended Availability SLO for {api} ({source})",
            Target=round(metrics["availability"], 4),
            Unit="percent",
            Window="28",
            Timestamp=timestamp,
        ),
        SLO(
            ServiceId=service_id,
            API=api,
            Type="Latency",
            Description=f"Recommended Latency SLO for {api} ({source})",
            Target=round(metrics["latency"], 4),
            Unit="p95",
            Window="28",
            Timestamp=timestamp,
        ),
        SLO(
            ServiceId=service_id,
            API=api,
            Type="ErrorRate",
            Description=f"Recommended ErrorRate SLO for {api} ({source})",
            Target=round(metrics["error_rate"], 4),
            Unit="percent",
            Window="28",
            Timestamp=timestamp,
        ),
    ]
