from datetime import timedelta
from datetime import datetime
from ColourText import format_text
import threading
import time
import os


class Timer:
    def __init__(self, project_name, sub_projects=None):
        if sub_projects is None:
            sub_projects = []
        self.proj_name = project_name
        self.sub_projs = sub_projects

        self.start_time = None
        self.end_time = None
        self.duration = None
        self.cntnue = True
        self.block_time = 300

        self.sub_projs = "[bright blue]" + "[reset], [bright blue]".join(self.sub_projs) + "[reset]"
        self.sub_projs = format(self.sub_projs.replace("\"", ""))

    def print_thread(self):
        blocks = 0
        while self.cntnue:
            time.sleep(self.block_time)
            if self.cntnue:
                print(format_text("[cyan]█[reset] "), end="")
                blocks += 1

                if blocks % 6 == 0:
                    print(" ", end="")
            else:
                return

    def start(self):
        self.start_time = time.time()
        print(format_text(f"Starting project [bright red]{self.proj_name}[reset]"
                          f" [{self.sub_projs}] at"
                          f" [bright green]{datetime.today().strftime('%X')}[reset]"))

    def stop(self):
        self.end_time = time.time()
        self.duration = timedelta(seconds=(time.time() - self.start_time))
        time_spent_str = format_text(f"[green][bold]{str(self.duration).split('.')[0]}[reset]")
        print(f"Timer stopped at {datetime.today().strftime('%X')},\nTime tracked: {time_spent_str}")

        return self.duration.seconds / 60

    # noinspection PyUnusedLocal
    def run_timer(self):
        self.start()
        print_thread = threading.Thread(target=self.print_thread)
        print_thread.daemon = True  # a daemon thread is supposed to die when the main func exits
        print_thread.start()

        """
        cmd_in = ""
        while cmd_in.lower() not in ["stop", "-s"]:
            cmd_in = input(">")
        """

        stop = input("")

        self.cntnue = False
        duration = self.stop()

        session_note = input("Session Note: ")
        return duration, session_note, self.start_time, self.end_time


def main():
    os.system("cls")
    timer = Timer("nothing", ["to", "see"])
    timer.run_timer()
    # print(f"{timer.run_timer()[0]} minutes")


if __name__ == "__main__":
    main()
