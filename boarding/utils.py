from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone


AIRPORT_TIME_ZONE = ZoneInfo("Africa/Lagos")


def get_check_in_window(flight, now=None):
    """Return the WAT check-in window state and its opening/closing times."""
    now = now or timezone.now()
    if timezone.is_naive(now):
        now = now.replace(tzinfo=AIRPORT_TIME_ZONE)
    now_wat = now.astimezone(AIRPORT_TIME_ZONE)

    departure_wat = datetime.combine(
        flight.departure_date,
        flight.departure_time,
    ).replace(tzinfo=AIRPORT_TIME_ZONE)
    opens_at = departure_wat - timedelta(hours=24)
    closes_at = departure_wat - timedelta(hours=1)

    if flight.status not in ("scheduled", "boarding"):
        state = "unavailable"
    elif now_wat < opens_at:
        state = "not_yet_open"
    elif now_wat >= closes_at:
        state = "closed"
    else:
        state = "open"

    return {"state": state, "opens_at": opens_at, "closes_at": closes_at}
