from commands import *
import argparse
import os

parser = argparse.ArgumentParser()
subparser = parser.add_subparsers(dest='command')

start = subparser.add_parser("start")
start.add_argument("project", type=str, help="name of project to be tracked for the session")
start.add_argument("-s", "--subs", type=str, nargs="+", default=[], help="list of sub-projects that are tracked"
                                                                         " along with main project")

status = subparser.add_parser("status")
status.add_argument("index", type=str, nargs="?", default=None, help="get status for a timer at a specific index"
                                                                     " in the active timers list. "
                                                                     "oldest/first timer starts at index 0")

remove = subparser.add_parser("remove")
remove.add_argument("index", type=str, nargs="?", default=None, help="remove timer from active timers list. "
                                                                     "timers are ordered from oldest to newest. "
                                                                     "oldest/first timer starts at index 0")

stop = subparser.add_parser("stop")
stop.add_argument("index", type=str, nargs="?", default=None, help="stop timer from active timers list. "
                                                                   "timers are ordered from oldest to newest. "
                                                                   "oldest/first timer starts at index 0")

projects = subparser.add_parser("projects")
aggregate = subparser.add_parser("aggregate")
clear_cmd = subparser.add_parser("clear")

sub_projects = subparser.add_parser("sub-projects")
sub_projects.add_argument("project", type=str, nargs="?", default="", help="name of project to"
                                                                           " print sub-projects list")

totals_cmd = subparser.add_parser("totals")
totals_cmd.add_argument("-prjs", "--projects", type=str, nargs="+", default=None, help="name of projects to be printed")

rename = subparser.add_parser("rename")
rename.add_argument("name", type=str, help="existing project's name")
rename.add_argument("new_name", type=str, help="new project name")

delete_proj = subparser.add_parser("delete")
delete_proj.add_argument("project", type=str, nargs="?", default="", help="name of project to be deleted")

log_cmd = subparser.add_parser("log")
log_cmd.add_argument("-prjs", "--projects", type=str, nargs="+", default=None, help="name of project(s) to show.")
log_cmd.add_argument("-p", "--period", type=int, nargs="?", default=None, help="number of days, starting from today,"
                                                                               " to print back to")

export_cmd = subparser.add_parser("export")
export_cmd.add_argument("projects", type=str, nargs="+", help="name of project(s) to be exported. "
                                                              "use 'all' to export everything")
export_cmd.add_argument("file", type=str, help="name of file to save exported project to. "
                                               "Will be located in the 'Exported' folder,")

import_cmd = subparser.add_parser("import")
import_cmd.add_argument("projects", type=str, nargs="+", help="name of project(s) to be imported")
import_cmd.add_argument("file", type=str, help="file to import project from. "
                                               "(Must be located in the 'Exported' folder")

chart_cmd = subparser.add_parser("chart")
chart_cmd.add_argument("projects", type=str, nargs="+", help="project names. use 'all' for all projects")
chart_cmd.add_argument("type", type=str, help="chart type, either 'pie' or 'bar'")

help_cmd = subparser.add_parser("help")

args = parser.parse_args()
load_pickles()

os.system("")
print()

if args.command is None:
    print(format_text("[cyan]Usage: AUTUMN COMMAND [ARGS]...[reset]\n"))
    print(format_text("[_text256]Autumn[reset] is a time tracking tool inspired by Watson\n"
                      "that allows the user to track the amount of time\n"
                      "they spend working on a given activity.\n\n"
                      "You just have to tell [_text256]Autumn[reset] when you start working\n"
                      "on your project with the `[green]start[reset]` command, and you can\n"
                      "stop the timer when you're done with the`[green]stop[reset]` command.\n\n"
                      "[underline][cyan]Commands:[reset]", 208
                      )
          )
    list_cmds()
elif args.command == 'start':
    start_command([args.project] + args.subs)
elif args.command == 'stop':
    stop_command(args.index if args.index else [])
elif args.command == 'status':
    status_command(args.index if args.index else [])
elif args.command == 'remove':
    remove_timer(args.index if args.index else [])
elif args.command == 'projects':
    list_projects()
elif args.command == 'sub-projects':
    list_subs([args.project] if args.project else [])
elif args.command == 'totals':
    show_totals(args.projects if args.projects else [])
elif args.command == 'rename':
    rename_project([args.name, args.new_name])
elif args.command == 'delete':
    delete_project([args.project] if args.project else [])

elif args.command == 'log':
    projects = args.projects if args.projects else ['all']
    period = [args.period] if args.period else []
    print(projects, period)
    get_logs(projects + period)

elif args.command == 'aggregate':
    get_aggregate()

elif args.command == 'export':
    projects = args.projects if args.projects else []
    file = [args.file] if args.file else []
    export(projects + file)

elif args.command == 'import':
    projects = args.projects if args.projects else []
    file = [args.file] if args.file else []
    import_exported(projects + file)

elif args.command == 'clear':
    clr()

elif args.command == 'chart':
    projects = args.projects if args.projects else []
    chartType = [args.type] if args.type else []
    chart(projects + chartType)

elif args.command == 'help':
    list_cmds()

print()
