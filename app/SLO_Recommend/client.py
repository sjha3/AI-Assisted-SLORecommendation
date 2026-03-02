import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
SLI_FILE = ROOT_DIR / "DB" / "SLI" / "ServiceSLI.csv"
SERVICE_CONFIG_DIR = ROOT_DIR / "DB" / "Config" / "Service"
DEP_GRAPH_FILE = ROOT_DIR / "DB" / "DepGraph" / "service_dependency_graph.json"
SLO_FILE_PRIMARY = ROOT_DIR / "DB" / "SLO" / "ServiceSLO.json"
SLO_FILE_FALLBACK = ROOT_DIR / "DB" / "SLO" / "Service_SLO.json"

logger = logging.getLogger(__name__)


def read_sli_rows() -> List[Dict[str, str]]:
    if not SLI_FILE.exists():
        raise FileNotFoundError(f"SLI data file not found: {SLI_FILE}")

    with SLI_FILE.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = [row for row in reader]
    logger.debug("Loaded SLI rows: %s", len(rows))
    return rows


def read_service_configs() -> List[Dict[str, object]]:
    if not SERVICE_CONFIG_DIR.exists():
        raise FileNotFoundError(f"Service config directory not found: {SERVICE_CONFIG_DIR}")

    rows: List[Dict[str, object]] = []
    for path in SERVICE_CONFIG_DIR.glob("*.json"):
        with path.open("r", encoding="utf-8") as file:
            rows.append(json.load(file))
    logger.debug("Loaded service configs: %s", len(rows))
    return rows


def get_service_category(service_id: str, api: Optional[str]) -> Optional[str]:
    logger.debug("Resolving service category for service_id=%s api=%s", service_id, api)
    configs = read_service_configs()
    category_by_service: Optional[str] = None

    for row in configs:
        if row.get("ServiceId") != service_id:
            continue

        category = row.get("Category")
        if isinstance(category, str):
            category_by_service = category

        configured_api = row.get("API")
        if api is None:
            continue

        if isinstance(configured_api, str) and configured_api == api:
            logger.debug("Resolved category=%s for exact API match", category_by_service)
            return category_by_service

        if isinstance(configured_api, list) and api in configured_api:
            logger.debug("Resolved category=%s for API list match", category_by_service)
            return category_by_service

    logger.debug("Resolved category=%s for service_id=%s", category_by_service, service_id)
    return category_by_service


def read_dependency_edges() -> List[Dict[str, str]]:
    if not DEP_GRAPH_FILE.exists():
        raise FileNotFoundError(f"Dependency graph file not found: {DEP_GRAPH_FILE}")

    with DEP_GRAPH_FILE.open("r", encoding="utf-8") as file:
        graph = json.load(file)

    edges = graph.get("edges", [])
    filtered_edges = [edge for edge in edges if isinstance(edge, dict)]
    logger.debug("Loaded dependency edges: %s", len(filtered_edges))
    return filtered_edges


def get_dependency_graph() -> Dict[Tuple[str, str], List[Tuple[str, str]]]:
    graph: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    for edge in read_dependency_edges():
        source = (edge.get("from_service_id", ""), edge.get("from_api", ""))
        target = (edge.get("to_service_id", ""), edge.get("to_api", ""))
        if not source[0] or not source[1] or not target[0] or not target[1]:
            continue
        graph.setdefault(source, []).append(target)
        graph.setdefault(target, graph.get(target, []))
    logger.debug("Constructed dependency graph nodes: %s", len(graph))
    return graph


def collect_reachable_nodes(
    root: Tuple[str, str],
    graph: Dict[Tuple[str, str], List[Tuple[str, str]]],
) -> Set[Tuple[str, str]]:
    visited: Set[Tuple[str, str]] = set()
    stack = [root]

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        stack.extend(graph.get(node, []))

    logger.debug("Reachable nodes from %s/%s: %s", root[0], root[1], len(visited))
    return visited


def read_static_slo_rows() -> List[Dict[str, object]]:
    slo_file = SLO_FILE_PRIMARY if SLO_FILE_PRIMARY.exists() else SLO_FILE_FALLBACK
    if not slo_file.exists():
        raise FileNotFoundError(f"SLO data file not found: {SLO_FILE_PRIMARY} or {SLO_FILE_FALLBACK}")

    with slo_file.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    slos = payload.get("slos", []) if isinstance(payload, dict) else []
    rows = [row for row in slos if isinstance(row, dict)]
    logger.debug("Loaded static SLO rows from %s: %s", slo_file, len(rows))
    return rows
