from datetime import datetime
from django.utils import timezone
import calendar
import pytz

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'


def parse_date_string_with_or_without_time(date_string):
    try:
        return datetime.strptime(date_string.strip(), '%Y-%m-%d %H:%M:%S')
    except ValueError:
        # If the time is not included, try again with date only
        return datetime.strptime(date_string.strip(), '%Y-%m-%d')


def unix_timestamp(d=None):
    if d is None:
        d = timezone.now()
        return calendar.timegm(d.utctimetuple())
    else:
        return calendar.timegm(d.timetuple())


def datesafe_eq(obj1, obj2):
    """
    If two objects are dates, but don't both have the same
    timezone awareness status, compare them in a timezone-safe way.
    Otherwise, compare them with regular equality.
    """
    if isinstance(obj1, datetime) and not timezone.is_aware(obj1):
        obj1 = timezone.make_aware(obj1, pytz.UTC)

    if isinstance(obj2, datetime) and not timezone.is_aware(obj2):
        obj2 = timezone.make_aware(obj2, pytz.UTC)

    return obj1 == obj2


def make_aware(value):
    if value is None or timezone.is_aware(value):
        return value
    else:
        return timezone.make_aware(value, timezone.utc)
