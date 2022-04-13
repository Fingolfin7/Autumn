from datetime import timedelta
from datetime import datetime
from ColourText import format_text
import time
import os


def td_str(td):
    hrs, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hrs > 0: hrs_str = f"{hrs} hours "
    else: hrs_str = ""

    if minutes > 0: min_str = f"{minutes} minutes "
    else: min_str = ""

    if seconds > 0: sec_str = f"{seconds} seconds "
    else: sec_str = ""

    return f"{hrs_str}{min_str}{sec_str}"


class Timer:
    def __init__(self, project_name, sub_projects=None):
        if sub_projects is None:
            sub_projects = []
        self.proj_name = project_name
        self.sub_projs = sub_projects

        self._start_time = None
        self._end_time = None
        self._duration = None

        self._formatted_subs = "[_text256_26_]" + "[reset], [_text256_26_]".join(self.sub_projs) + "[reset]"

    def start(self):
        self._start_time = time.time()
        print(format_text(f"Started [bright red]{self.proj_name}[reset]"
                          f" [{self._formatted_subs}] at"
                          f" [_text256_34_]{datetime.today().strftime('%X')}[reset]"))

    def time_spent(self):
        self._duration = timedelta(seconds=(time.time() - self._start_time))
        print(format_text(f"Started "
                          f"[bright red]{self.proj_name}[reset] [{self._formatted_subs}], "
                          f"[_text256_34_]{td_str(self._duration)}[reset]ago"))

    def stop(self):
        self._end_time = time.time()
        self._duration = timedelta(seconds=(time.time() - self._start_time))

        print(format_text(f"Stopping [bright red]{self.proj_name}[reset] "
                          f"[{self._formatted_subs}] at {datetime.today().strftime('%X')}, "
                          f"started [_text256_34_]{td_str(self._duration)}[reset]ago"))

        duration = self._duration.seconds / 60
        session_note = input("Session Note: ").strip()
        return duration, session_note, self._start_time, self._end_time


def main():
    os.system("cls")
    timer = Timer("nothing", ["to", "see"])
    timer.start()
    time.sleep(5)
    timer.time_spent()
    # print(f"{timer.run_timer()[0]} minutes")


if __name__ == "__main__":
    main()
