import logging
from datetime import datetime
from typing import List, Optional

try:
    from .client import read_sli_rows
    from .model.sli_model import SLI
except ImportError:
    from client import read_sli_rows
    from model.sli_model import SLI

logger = logging.getLogger(__name__)


def _parse_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _subtract_months(dt: datetime, months: int) -> datetime:
    year = dt.year
    month = dt.month - months
    while month <= 0:
        month += 12
        year -= 1
    return dt.replace(year=year, month=month)


def _filter_slis(rows: List[SLI], service_id: Optional[str], api: Optional[str]) -> List[SLI]:
    filtered = rows
    if service_id:
        filtered = [row for row in filtered if row.ServiceId == service_id]
    if api:
        filtered = [row for row in filtered if row.API == api]
    return filtered


def _latest_rows(rows: List[SLI]) -> List[SLI]:
    latest_ts = max(_parse_timestamp(row.Timestamp) for row in rows)
    return [row for row in rows if _parse_timestamp(row.Timestamp) == latest_ts]


def get_latest_sli_data(service_id: Optional[str], api: Optional[str]) -> List[SLI]:
    rows = read_sli_rows()
    filtered = _filter_slis(rows, service_id, api)
    if not filtered:
        return []

    latest = _latest_rows(filtered)
    logger.info("Latest SLI query returned %s rows", len(latest))
    return latest


def get_sli_data(
    service_id: Optional[str],
    api: Optional[str],
    number_of_months: Optional[int],
) -> List[SLI]:
    rows = read_sli_rows()
    filtered = _filter_slis(rows, service_id, api)
    if not filtered:
        return []

    if number_of_months is None:
        latest = _latest_rows(filtered)
        logger.info("SLI query without number_of_months returned %s latest rows", len(latest))
        return latest

    latest_ts = max(_parse_timestamp(row.Timestamp) for row in filtered)
    cutoff_ts = _subtract_months(latest_ts, number_of_months - 1)

    window_rows = [row for row in filtered if _parse_timestamp(row.Timestamp) >= cutoff_ts]
    window_rows.sort(key=lambda row: _parse_timestamp(row.Timestamp), reverse=True)

    logger.info(
        "SLI query with number_of_months=%s returned %s rows",
        number_of_months,
        len(window_rows),
    )
    return window_rows
