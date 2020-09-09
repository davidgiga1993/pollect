import datetime


def iso_to_time(timestamp: str):
    date = datetime.datetime.strptime(timestamp.replace(':', ''), "%Y-%m-%dT%H%M%S.%fZ")
    return date.replace(tzinfo=datetime.timezone.utc)


def add_month(date: datetime.datetime):
    date = date.replace(day=1)
    month = date.month
    if month == 12:
        date = date.replace(year=date.year + 1)
        month = 1
    else:
        month += 1
    return date.replace(month=month)


def sub_month(date: datetime.datetime):
    date = date.replace(day=1)
    month = date.month
    if month == 1:
        date = date.replace(year=date.year - 1)
        month = 12
    else:
        month -= 1
    return date.replace(month=month)
