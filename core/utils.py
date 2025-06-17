from datetime import datetime, date, timedelta, timezone


def get_utc4_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=4)))

def get_utc4_today() -> date:
    return get_utc4_now().date()