from datetime import datetime
from typing import List

try:
    from .client import read_incident_rows
    from .model.incident_model import Incident
except ImportError:
    from client import read_incident_rows
    from model.incident_model import Incident


def _parse_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def get_incidents_for_service_api_in_period(
    service_id: str,
    api: str,
    start_time: str,
    end_time: str,
) -> List[Incident]:
    start_dt = _parse_timestamp(start_time)
    end_dt = _parse_timestamp(end_time)

    if start_dt > end_dt:
        raise ValueError("start_time must be less than or equal to end_time")

    incidents = read_incident_rows()

    filtered = []
    for incident in incidents:
        if incident.ServiceId != service_id:
            continue
        if incident.API != api:
            continue

        incident_dt = _parse_timestamp(incident.Timestamp)
        if start_dt <= incident_dt <= end_dt:
            filtered.append(incident)

    filtered.sort(key=lambda x: _parse_timestamp(x.Timestamp), reverse=True)
    return filtered
