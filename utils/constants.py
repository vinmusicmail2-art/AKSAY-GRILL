SHOW_PENDING = "pending"
SHOW_PROCESSED = "processed"
SHOW_ALL = "all"

SORT_DATE_DESC = "date_desc"
SORT_DATE_ASC = "date_asc"
SORT_GUESTS_DESC = "guests_desc"
SORT_GUESTS_ASC = "guests_asc"

PERIOD_TODAY = "today"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
PERIOD_ALL = "all"

DATE_FORMAT_DISPLAY = "%d.%m.%Y %H:%M"
DATE_FORMAT_FILENAME = "%Y%m%d_%H%M"


def format_display_date(dt) -> str:
    """Format datetime for display."""
    return dt.strftime(DATE_FORMAT_DISPLAY) if dt else ""


def format_filename_date(dt) -> str:
    """Format datetime for filename."""
    return dt.strftime(DATE_FORMAT_FILENAME) if dt else ""
