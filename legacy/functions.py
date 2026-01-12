from datetime import timedelta
from datetime import datetime


def listOfDates(fromDate: str, toDate: str):
    fromDate = datetime.strptime(fromDate, "%m-%d-%Y") \
        if fromDate else datetime.today() - timedelta(days=7)
    toDate = datetime.strptime(toDate, "%m-%d-%Y") \
        if toDate else datetime.today()

    # if fromDate > toDate and fromDate and not toDate

    if fromDate > toDate:
        return None

    return [(toDate + timedelta(days=-i)).strftime("%m-%d-%Y") for i in range((toDate - fromDate).days + 1)]


def td_str(td: timedelta):
    """
    Converts timedelta objects into formatted time strings showing durations. E.g. 1 day 2 hours 28 minutes 56 seconds
    :param td: timedelta objects
    :return: string formatted to days, hours, minutes and seconds.
    """
    days = td.days
    hrs, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    plural_form = lambda counter: 's'[:counter ^ 1]

    if days > 0:
        days_str = f"{days} day{plural_form(days)} "
    else:
        days_str = ""

    if hrs > 0:
        hrs_str = f"{hrs} hour{plural_form(hrs)} "
    else:
        hrs_str = ""

    if minutes > 0:
        min_str = f"{minutes} minute{plural_form(minutes)} "
    else:
        min_str = ""

    if seconds > 0:
        sec_str = f"{seconds} second{plural_form(seconds)} "
    else:
        sec_str = ""

    return f"{days_str}{hrs_str}{min_str}{sec_str}"


def get_date_last(period_str: str):
    """
    :param period_str: Year, month, fortnight, week, day
    :return: the date formatted as a string
    """
    today = datetime.today()
    if period_str == 'year':  # back to the first day of the year
        return f"01-01-{today.year}"
    elif period_str == 'month':  # back to the first day of the month
        return (today - timedelta(days=today.day-1)).strftime("%m-%d-%Y")
    elif period_str == 'fortnight':
        return (today - timedelta(days=14)).strftime("%m-%d-%Y")
    elif period_str == 'week':
        return (today - timedelta(days=7)).strftime("%m-%d-%Y")
    elif period_str == 'day':
        return today.strftime("%m-%d-%Y")
