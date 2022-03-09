from commands import *
from ColourText import format_text
import os

AUTUMN = format_text('[bold][_text256]Autumn>[reset]', 208)

commands = {
    "commands": list_cmds,
    "start": start_command,
    "projects": list_projects,
    "sub-projects": list_subs,
    "log": get_logs,
    "aggregate": get_aggregate,
    "clear": clr,
    "chart": chart,
    "quit": quit_autumn
}


def main():
    os.system("cls")
    while True:
        cmd_in = input(f"{AUTUMN} ")
        print()
        cmd_in, arguments = parse_command(cmd_in)
        if cmd_in in commands:
            commands[cmd_in](arguments)
        print()


if __name__ == "__main__":
    main()
