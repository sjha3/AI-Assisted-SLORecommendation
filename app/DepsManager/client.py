import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
GRAPH_DB_DIR = (BASE_DIR / ".." / "DB" / "DepGraph").resolve()
GRAPH_DB_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_DB_FILE = GRAPH_DB_DIR / "service_dependency_graph.json"


def read_graph() -> Dict[str, Any]:
    if not GRAPH_DB_FILE.exists():
        return {"nodes": [], "edges": []}

    with GRAPH_DB_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "nodes" not in data:
        data["nodes"] = []
    if "edges" not in data:
        data["edges"] = []
    return data


def write_graph(graph: Dict[str, Any]) -> None:
    with GRAPH_DB_FILE.open("w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)
    logger.info("Graph DB updated at %s", GRAPH_DB_FILE)
