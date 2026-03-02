import json
import logging
from pathlib import Path
from typing import List

try:
    from .model.slo_model import SLO
except ImportError:
    from model.slo_model import SLO

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
SLO_FILE_PATH = (BASE_DIR / ".." / "DB" / "SLO" / "ServiceSLO.json").resolve()


def read_slo_rows() -> List[SLO]:
    if not SLO_FILE_PATH.exists():
        raise FileNotFoundError(f"SLO source file not found: {SLO_FILE_PATH}")

    with SLO_FILE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    normalized = []
    for item in data.get("slos", []):
        row = dict(item)
        if "Window" in row:
            row["Window"] = row.pop("Window")
        normalized.append(row)

    slos = [SLO(**item) for item in normalized]
    logger.info("Read %s SLO rows from %s", len(slos), SLO_FILE_PATH)
    return slos
