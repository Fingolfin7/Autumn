from datetime import timedelta
from datetime import datetime
from ColourText import format_text
import time
import os


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
                          f" [bright green]{datetime.today().strftime('%X')}[reset]"))

    def time_spent(self):
        time_passed = timedelta(seconds=(time.time() - self._start_time))
        print(format_text(f"Time passed on "
                          f"[bright red]{self.proj_name}[reset] [{self._formatted_subs}]: "
                          f"[bright green]{str(time_passed).split('.')[0]}[reset]"))

    def stop(self):
        self._end_time = time.time()
        self._duration = timedelta(seconds=(time.time() - self._start_time))
        time_spent_str = f"[green][bold]{str(self._duration).split('.')[0]}[reset]"

        print(format_text(f"Stopped [bright red]{self.proj_name}[reset] "
                          f"stopped at {datetime.today().strftime('%X')},\n"
                          f"Time tracked: {time_spent_str}"))

        duration = self._duration.seconds / 60
        session_note = input("Session Note: ")
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
