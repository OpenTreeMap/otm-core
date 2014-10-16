from datetime import datetime

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'


def parse_date_string_with_or_without_time(date_string):
    try:
        return datetime.strptime(date_string.strip(), '%Y-%m-%d %H:%M:%S')
    except ValueError:
        # If the time is not included, try again with date only
        return datetime.strptime(date_string.strip(), '%Y-%m-%d')
