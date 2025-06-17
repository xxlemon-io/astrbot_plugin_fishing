from datetime import datetime, date, timedelta, timezone

# 获取当前的UTC+8时间
def get_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))

def get_today() -> date:
    return get_now().date()