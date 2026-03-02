import json
import logging
from pathlib import Path
from typing import List

try:
    from .model.incident_model import Incident
except ImportError:
    from model.incident_model import Incident

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
INCIDENTS_FILE_PATH = (BASE_DIR / ".." / "DB" / "Incidents" / "incidents.json").resolve()


def read_incident_rows() -> List[Incident]:
    if not INCIDENTS_FILE_PATH.exists():
        raise FileNotFoundError(f"Incidents source file not found: {INCIDENTS_FILE_PATH}")

    with INCIDENTS_FILE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    incidents = [Incident(**item) for item in data.get("incidents", [])]
    logger.info("Read %s incidents from %s", len(incidents), INCIDENTS_FILE_PATH)
    return incidents
