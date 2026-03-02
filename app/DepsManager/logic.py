import logging
from collections import deque
from typing import Any, Dict, List

'''
try:
    from .client import read_graph, write_graph
    from .model.model import BatchDepsCreateRequest
except ImportError:
    from client import read_graph, write_graph
    from app.DepsManager.model.model import BatchDepsCreateRequest
'''
from model.model import BatchDepsCreateRequest
from client import read_graph, write_graph
logger = logging.getLogger(__name__)


def _node(service_id: str) -> Dict[str, str]:
    return {"service_id": service_id}


def _edge(from_service_id: str, from_api: str, to_service_id: str, to_api: str) -> Dict[str, str]:
    return {
        "from_service_id": from_service_id,
        "from_api": from_api,
        "to_service_id": to_service_id,
        "to_api": to_api,
    }


def store_dependencies_in_graph(request: BatchDepsCreateRequest) -> Dict[str, Any]:
    graph = read_graph()

    node_set = {n["service_id"] for n in graph["nodes"]}
    edge_set = {
        (e["from_service_id"], e["from_api"], e["to_service_id"], e["to_api"])
        for e in graph["edges"]
    }

    added_nodes = 0
    added_edges = 0

    for dep in request.dependencies:
        if dep.ServiceId not in node_set:
            graph["nodes"].append(_node(dep.ServiceId))
            node_set.add(dep.ServiceId)
            added_nodes += 1

        for depends_on in dep.DependsOn:
            if depends_on.ServiceId not in node_set:
                graph["nodes"].append(_node(depends_on.ServiceId))
                node_set.add(depends_on.ServiceId)
                added_nodes += 1

            ek = (dep.ServiceId, dep.API, depends_on.ServiceId, depends_on.API)
            if ek not in edge_set:
                graph["edges"].append(
                    _edge(
                        from_service_id=dep.ServiceId,
                        from_api=dep.API,
                        to_service_id=depends_on.ServiceId,
                        to_api=depends_on.API,
                    )
                )
                edge_set.add(ek)
                added_edges += 1

    write_graph(graph)
    logger.info("Stored dependencies in graph. added_nodes=%s added_edges=%s", added_nodes, added_edges)

    return {
        "message": "Dependencies stored in graph DB",
        "added_nodes": added_nodes,
        "added_edges": added_edges,
        "total_nodes": len(graph["nodes"]),
        "total_edges": len(graph["edges"]),
    }


def get_service_dependencies(service_id: str) -> Dict[str, Any]:
    graph = read_graph()

    outgoing = [
        e for e in graph["edges"] if e["from_service_id"] == service_id
    ]
    incoming = [
        e for e in graph["edges"] if e["to_service_id"] == service_id
    ]

    return {
        "service_id": service_id,
        "depends_on": outgoing,
        "depended_by": incoming,
    }


def get_dependency_between(source_service_id: str, target_service_id: str) -> Dict[str, Any]:
    graph = read_graph()
    edges = graph["edges"]

    adjacency: Dict[str, List[str]] = {}
    for e in edges:
        adjacency.setdefault(e["from_service_id"], []).append(e["to_service_id"])

    direct = any(
        e["from_service_id"] == source_service_id and e["to_service_id"] == target_service_id
        for e in edges
    )

    queue = deque([(source_service_id, [source_service_id])])
    visited = {source_service_id}
    shortest_path: List[str] = []

    while queue:
        current, path = queue.popleft()
        if current == target_service_id:
            shortest_path = path
            break

        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return {
        "source_service_id": source_service_id,
        "target_service_id": target_service_id,
        "direct_dependency": direct,
        "path_exists": len(shortest_path) > 0,
        "shortest_path": shortest_path,
    }


def get_downstream_nodes(service_id: str) -> Dict[str, Any]:
    graph = read_graph()
    edges = graph["edges"]

    adjacency: Dict[str, List[str]] = {}
    for e in edges:
        adjacency.setdefault(e["from_service_id"], []).append(e["to_service_id"])

    queue = deque([service_id])
    visited = {service_id}
    downstream: List[str] = []

    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                downstream.append(neighbor)
                queue.append(neighbor)

    return {
        "service_id": service_id,
        "downstream_nodes": downstream,
        "count": len(downstream),
    }


def get_full_graph() -> Dict[str, Any]:
    graph = read_graph()
    logger.info(
        "Fetched full dependency graph: nodes=%s edges=%s",
        len(graph.get("nodes", [])),
        len(graph.get("edges", [])),
    )
    return graph
