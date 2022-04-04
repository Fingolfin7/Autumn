from commands import *
from ColourText import format_text
import os

AUTUMN = format_text('[_text256]Autumn>[reset]', 208)
input_color = format_text("[green]")
reset = format_text("[reset]")

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
    "start": start_command,
    "stop": stop_command,
    "status": status_command,
    "sub-projects": list_subs,
    "totals": show_totals,
}


def main():
    os.system("")
    while True:
        try:
            cmd_in = input(f"{AUTUMN} {input_color}")
            print(reset)
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
