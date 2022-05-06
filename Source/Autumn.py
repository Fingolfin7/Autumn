from commands import *
from ColourText import format_text
from commands import load_pickles
import os
import signal
import atexit

AUTUMN = format_text('[_text256]Autumn>[reset]', 208)
input_color = format_text("[green]")
reset = format_text("[reset]")

# exit handler
atexit.register(quit_autumn)
signal.signal(signal.SIGTERM, quit_autumn)
signal.signal(signal.SIGINT, quit_autumn)

commands = {
    "aggregate": get_aggregate,
    "chart": chart,
    "clear": clr,
    "commands": list_cmds,
    "delete": delete_project,
    "export": export,
    "import": import_exported,
    "log": get_logs,
    "print": print_project,
    "projects": list_projects,
    "quit": quit_autumn,
    "remove-timer": remove_timer,
    "rename": rename_project,
    "start": start_command,
    "stop": stop_command,
    "status": status_command,
    "sub-projects": list_subs,
    "totals": show_totals,
}


def main():
    os.system("")
    load_pickles()
    while True:
        cmd_in = input(f"{AUTUMN} {input_color}")
        print(reset)
        try:
            cmd_in, arguments = parse_command(cmd_in)

            if cmd_in in commands:
                try:
                    commands[cmd_in](arguments)
                except TypeError:
                    commands[cmd_in]()

        except IndexError:
            print(f"Too few arguments for command: {cmd_in}!")

        except KeyboardInterrupt:
            print(f"{reset}Quitting.")
            quit_autumn()

        print()


if __name__ == "__main__":
    main()
