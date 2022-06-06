from arg_parse_cmds import *
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
totals_cmd.add_argument("--projects", type=str, nargs="+", default=None, help="name of projects to be printed")

rename = subparser.add_parser("rename")
rename.add_argument("name", type=str, help="existing project's name")
rename.add_argument("new_name", type=str, help="new project name")

delete_proj = subparser.add_parser("delete")
delete_proj.add_argument("project", type=str, nargs="?", default="", help="name of project to be deleted")

log_cmd = subparser.add_parser("log")
log_cmd.add_argument("--projects", type=str, nargs="+", default="all", help="name of project(s) to show.")
log_cmd.add_argument("--period", type=int, nargs="?", default=None, help="number of days, starting from today,"
                                                                         " to print back to")

export_cmd = subparser.add_parser("export")
export_cmd.add_argument("projects", type=str, nargs="+",  help="name of project(s) to be exported. "
                                                               "use 'all' to export everything")
export_cmd.add_argument("file", type=str, help="name of file to save exported project to. "
                                               "Will be loacted in the 'Exported' folder,")

import_cmd = subparser.add_parser("import")
import_cmd.add_argument("projects", type=str, nargs="+", help="name of project(s) to be imported")
import_cmd.add_argument("file", type=str, help="file to import project from. "
                                               "(Must be located in the 'Exported' folder")

chart_cmd = subparser.add_parser("chart")
chart_cmd.add_argument("projects", type=str, nargs="+", help="project names. use 'all' for all projects")
chart_cmd.add_argument("type", type=str, help="chart type, either 'pie' or 'bar'")

args = parser.parse_args()
load_pickles()
os.system("")

if args.command == 'start':
    start_command(args.project, args.subs)
elif args.command == 'stop':
    stop_command(args.index)
elif args.command == 'status':
    status_command(args.index)
elif args.command == 'remove':
    remove_timer(args.index)
elif args.command == 'projects':
    list_projects()
elif args.command == 'sub-projects':
    list_subs(args.project)
elif args.command == 'totals':
    show_totals(args.projects)
elif args.command == 'rename':
    rename_project(args.name, args.new_name)
elif args.command == 'delete':
    delete_project(args.project)
elif args.command == 'log':
    get_logs(args.projects, args.period)
elif args.command == 'aggregate':
    get_aggregate()
elif args.command == 'export':
    export(args.projects, args.file)
elif args.command == 'import':
    import_exported(args.projects, args.file)
elif args.command == 'clear':
    clr()
elif args.command == 'chart':
    chart(args.projects, args.type)
