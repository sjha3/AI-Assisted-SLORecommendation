import csv
import logging
from pathlib import Path
from typing import List

try:
    from .model.sli_model import SLI
except ImportError:
    from model.sli_model import SLI

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
TARGET_DIR = (BASE_DIR / ".." / "DB" /  "SLI").resolve()
SLI_CSV_PATH = TARGET_DIR / "ServiceSLI.csv"


def read_sli_rows() -> List[SLI]:
    if not SLI_CSV_PATH.exists():
        raise FileNotFoundError(f"SLI csv not found: {SLI_CSV_PATH}")

    with SLI_CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows: List[SLI] = []
        for row in reader:
            rows.append(
                SLI(
                    ServiceId=str(row["ServiceId"]),
                    API=str(row["API"]),
                    Type=str(row["Type"]),
                    Description=str(row["Description"]),
                    Value=float(row["Value"]),
                    Unit=str(row["Unit"]),
                    Window=str(row["Window"]),
                    Timestamp=str(row["Timestamp"]),
                )
            )

    logger.info("Read %s SLI rows from %s", len(rows), SLI_CSV_PATH)
    return rows
