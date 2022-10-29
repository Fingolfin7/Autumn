from datetime import timedelta
from datetime import datetime
from ColourText import format_text
import time


def td_str(td: timedelta):
    """
    Converts timedelta objects into formatted time strings showing durations. E.g. 1 day 2 hours 28 minutes 56 seconds
    :param td: timedelta objects
    :return: string formated to days, hours, minutes and seconds.
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


class Timer:
    def __init__(self, project_name, sub_projects=None):
        """
        :param project_name: name of existing project
        :param sub_projects: list of project sub-projects
        """
        if sub_projects is None:
            sub_projects = []
        self.proj_name = project_name
        self.sub_projs = sub_projects

        self._start_time = None
        self._end_time = None
        self._duration = None

        self._formatted_subs = "[_text256_26_]" + "[reset], [_text256_26_]".join(self.sub_projs) + "[reset]"

    def start(self):
        """
        Start tracking a new session
        """
        self._start_time = time.time()
        print(format_text(f"Started [bright red]{self.proj_name}[reset]"
                          f" [{self._formatted_subs}] at"
                          f" [_text256_34_]{datetime.today().strftime('%X')}[reset]"))

    def restart(self):
        """
        Restart tracking an existing session timer
        """
        self._start_time = time.time()
        print(format_text(f"Restated [bright red]{self.proj_name}[reset]"
                          f" [{self._formatted_subs}] at"
                          f" [_text256_34_]{datetime.today().strftime('%X')}[reset]"))

    def time_spent(self):
        """
        Print how much time has started since the start of the session
        :return:
        """
        self._duration = timedelta(seconds=(time.time() - self._start_time))
        print(format_text(f"Started "
                          f"[bright red]{self.proj_name}[reset] [{self._formatted_subs}], "
                          f"[_text256_34_]{td_str(self._duration)}[reset]ago"))

    def stop(self):
        """
        Stop tracking project session

        :return: session duration, note, start and end time
        """
        self._end_time = time.time()
        self._duration = timedelta(seconds=(time.time() - self._start_time))

        print(format_text(f"Stopped [bright red]{self.proj_name}[reset] "
                          f"[{self._formatted_subs}] at {datetime.today().strftime('%X')}, "
                          f"started [_text256_34_]{td_str(self._duration)}[reset]ago"))

        duration = self._duration.seconds / 60
        session_note = input("Session Note: ").strip()
        return duration, session_note, self._start_time, self._end_time
