from commands import *
from ColourText import format_text
from commands import load_pickles
import os


AUTUMN = format_text('[_text256]Autumn>[reset]', 208)
input_color = format_text("[green]")
reset = format_text("[reset]")

commands = {
    "aggregate": get_aggregate,
    "chart": chart,
    "clear": clr,
    "delete": delete_project,
    "export": export,
    "help": list_cmds,
    "import": import_exported,
    "log": get_logs,
    "print": print_project,
    "projects": list_projects,
    "quit": quit_autumn,
    "remove": remove_timer,
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

        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"{reset}Quitting.")
        quit_autumn()
