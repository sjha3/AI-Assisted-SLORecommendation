from datetime import datetime
from typing import List, Optional

try:
    from .client import read_slo_rows
    from .model.slo_model import SLO
except ImportError:
    from client import read_slo_rows
    from model.slo_model import SLO


def _parse_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def get_slos_for_service(
    service_id: str,
    api: Optional[str] = None,
    slo_type: Optional[str] = None,
) -> List[SLO]:
    rows = read_slo_rows()
    filtered = [row for row in rows if row.ServiceId == service_id]

    if api:
        filtered = [row for row in filtered if row.API == api]

    if slo_type:
        filtered = [row for row in filtered if row.Type.lower() == slo_type.lower()]

    return filtered


def get_latest_slos_for_service(
    service_id: str,
    api: Optional[str] = None,
    slo_type: Optional[str] = None,
) -> List[SLO]:
    filtered = get_slos_for_service(service_id=service_id, api=api, slo_type=slo_type)
    if not filtered:
        return []

    latest_timestamp = max(_parse_timestamp(row.Timestamp) for row in filtered)
    return [row for row in filtered if _parse_timestamp(row.Timestamp) == latest_timestamp]
