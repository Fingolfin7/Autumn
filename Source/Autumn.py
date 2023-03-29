from commands import *
from functions import get_date_last
import argparse
import os

parser = argparse.ArgumentParser()
subparser = parser.add_subparsers(dest='command')

start = subparser.add_parser("start")
start.add_argument("project", type=str, help="name of project to be tracked for the session")
start.add_argument("-s", "--subs", type=str, nargs="+", default=[], help="list of sub-projects that are tracked"
                                                                         " along with main project")

restart = subparser.add_parser("restart")
restart.add_argument("index", type=int, nargs="?", default=None, help="restart timer from active timers list. "
                                                                     "timers are ordered from oldest to newest. "
                                                                     "oldest/first timer starts at index 0")


status = subparser.add_parser("status")
status.add_argument("index", type=int, nargs="?", default=None, help="get status for a timer at a specific index"
                                                                     " in the active timers list. "
                                                                     "oldest/first timer starts at index 0")

remove = subparser.add_parser("remove")
remove.add_argument("index", type=int, nargs="?", default=None, help="remove timer from active timers list. "
                                                                     "timers are ordered from oldest to newest. "
                                                                     "oldest/first timer starts at index 0")

stop = subparser.add_parser("stop")
stop.add_argument("index", type=int, nargs="?", default=None, help="stop timer from active timers list. "
                                                                   "timers are ordered from oldest to newest. "
                                                                   "oldest/first timer starts at index 0")

track = subparser.add_parser("track")
track.add_argument('start', type=str, help="Session start time. Format of month-day-year-Hour:Minute")
track.add_argument('end', type=str, help="Session end time. Format of month-day-year-Hour:Minute")
track.add_argument("project", type=str, help="name of project to be tracked for the session")
track.add_argument("-s", "--subs", type=str, nargs="+", default=[], help="list of sub-projects that are tracked")
track.add_argument("-sn", '--note', type=str, default="", help="Session note.")

WatsonExport = subparser.add_parser("WatsonExport")
WatsonExport.add_argument("project", type=str, help="name of project to be exported to Watson")

projects = subparser.add_parser("projects")

sub_projects = subparser.add_parser("subprojects")
sub_projects.add_argument("project", type=str, nargs="?", default="", help="name of project to"
                                                                           " print subprojects list")

totals_cmd = subparser.add_parser("totals")
totals_cmd.add_argument("-p", "--projects", type=str, nargs="+", default=None, help="name of projects to be printed")
totals_cmd.add_argument("-st", "--status", type=str, nargs="?", default=None, help="Filter by project status. "
                                                                       "Either 'active', 'paused' or 'complete'")


# rename = subparser.add_parser("rename")
# rename.add_argument("name", type=str, help="existing project's name")
# rename.add_argument("new_name", type=str, help="new project name")

# command to rename projects or subprojects
rename_cmd = subparser.add_parser("rename")
rename_cmd.add_argument("project", type=str, help="existing project's name")
rename_cmd.add_argument("-s", "--sub_name", type=str, help="list of sub-projects that are tracked")
rename_cmd.add_argument("-nn","--new_name", type=str, help="new project name")
rename_cmd.add_argument("-ns","--new_sub_name", type=str, help="new sub-project name")


delete_proj = subparser.add_parser("delete")
delete_proj.add_argument("project", type=str, nargs="?", default="", help="name of project to be deleted")

mark_project = subparser.add_parser("mark")
mark_project.add_argument("project", type=str, nargs="?", default="", help="name of project to update status")
mark_project.add_argument("status", type=str, nargs="?", default="", help="project status. "
                                                                          "Either 'active', 'paused' or 'complete'")

log_cmd = subparser.add_parser("log")
log_cmd.add_argument("-p", "--projects", type=str, nargs="+", default='all', help="name of project(s) to show.")
log_cmd.add_argument("-f", "--fromDate", type=str, default=None, help="date to start log from")
log_cmd.add_argument("-t", "--toDate", type=str, default=None, help="date to start log from")
log_cmd.add_argument("-pd", "--period", type=str, default=None, help="logs for the last day/week/fortnight/month/year")
log_cmd.add_argument("-x", "--hide_notes", action="store_true", help="exclude session notes in log output")
log_cmd.add_argument("-m", "--max_note_length", type=int, default=300, help="maximum session note length before truncation")
log_cmd.add_argument("-st", "--status", type=str, nargs="?", default=None, help="Filter by project status. "
                                                                       "Either 'active', 'paused' or 'complete'")
# log_cmd.add_argument("-d", "--days", type=int, nargs="?", default=7, help="number of days, starting from today,"
#                                                                               " to print back to")

export_cmd = subparser.add_parser("export")
export_cmd.add_argument("-p", "--projects", type=str, nargs="+", help="name of project(s) to be exported.")
export_cmd.add_argument("-f", "--file", type=str, help="name of file to save exported project to. "
                                               "Will be located in the 'Exported' folder,")

import_cmd = subparser.add_parser("import")
import_cmd.add_argument("-p", "--projects", type=str, nargs="+", default="", help="name of project(s) to be imported")
import_cmd.add_argument("-f", "--file", type=str, help="file to import project(s) from. "
                                               "(Must be located in the base directory's 'Exported' folder)")

chart_cmd = subparser.add_parser("chart")
chart_cmd.add_argument("-p", "--projects", type=str, nargs="+", default="all", help="project names. use 'all' for all "
                                                                                    "projects")
chart_cmd.add_argument("-t", "--type", type=str, default="pie", help="chart type, either 'pie' or 'bar'")
chart_cmd.add_argument("-st", "--status", type=str, nargs="?", default=None, help="Filter by project status. "
                                                                       "Either 'active', 'paused' or 'complete'")

merge_cmd = subparser.add_parser("merge")
merge_cmd.add_argument("project1", type=str, help="name of first project to be merged")
merge_cmd.add_argument("project2", type=str, help="name of second project to be merged")
merge_cmd.add_argument("merged_name", type=str, help="name of the merged project")

# add sync command
sync_cmd = subparser.add_parser("sync")
sync_cmd.add_argument("-f", "--file", type=str, help="File to sync with. ")
sync_cmd.add_argument("-r", "--remote", action="store_true", help="is the file a network file?")

help_cmd = subparser.add_parser("help")

args = parser.parse_args()
load_pickles()

os.system("")
print()

if args.command is None:
    print(format_text("[_text256]Autumn[reset] is a time tracking tool inspired by Watson\n"
                      "that allows the user to track the amount of time\n"
                      "they spend working on a given activity.\n\n"
                      "[cyan]Usage: AUTUMN COMMAND -h, --help [ARGS]...[reset]\n\n"
                      "You just have to tell [_text256]Autumn[reset] when you start working\n"
                      "on your project with the `[green]start[reset]` command, and you can\n"
                      "stop the timer when you're done with the `[green]stop[reset]` command\n"
                      "and add an optional session note.\n", 208))
    help()
elif args.command == 'start':
    start_command(args.project, args.subs)
elif args.command == 'stop':
    stop_command(args.index) if args.index else stop_command()
elif args.command == 'status':
    status_command(args.index) if args.index else status_command()
elif args.command == 'track':
    track_project(args.start, args.end, args.project, args.subs, args.note)
elif args.command == 'remove':
    remove_timer(args.index)
elif args.command == 'restart':
    restart_command(args.index) if args.index else restart_command()
elif args.command == 'projects':
    list_projects()
elif args.command == "WatsonExport":
    export_to_watson(args.project)
elif args.command == 'subprojects':
    list_subs(args.project)
elif args.command == 'totals':
    if args.projects:
        show_totals(args.projects, args.status)
    elif args.status and not args.projects:
        show_totals("all", args.status)
    else:
        show_totals()
elif args.command == 'rename':
    if args.sub_name and args.new_sub_name:
        rename_subproject(args.project, args.sub_name, args.new_sub_name)
    elif args.project and args.new_name:
        rename_project(args.project, args.new_name)
elif args.command == 'delete':
    delete_project(args.project)
elif args.command == 'log':
    if args.period:
        get_logs(projects=args.projects, fromDate=get_date_last(args.period), toDate=args.toDate,
                 status=args.status, sessionNote=not args.hide_notes, noteLength=args.max_note_length)
    else:
        get_logs(projects=args.projects, fromDate=args.fromDate, toDate=args.toDate,
                 status=args.status, sessionNote=not args.hide_notes, noteLength=args.max_note_length)
elif args.command == 'mark':
    funcs_switch = {'active': mark_project_active,
                    'paused': mark_project_paused,
                    'complete': mark_project_complete
                    }
    funcs_switch[args.status](args.project)
elif args.command == 'export':
    export(args.projects, args.file)
elif args.command == 'import':
    import_exported(args.projects, args.file)
elif args.command == 'chart':
    chart(args.projects, args.type, args.status)
elif args.command == 'merge':
    merge_projects(args.project1, args.project2, args.merged_name)
elif args.command == 'sync':
    sync_projects(args.file, not args.remote)
elif args.command == 'help':
    help()

print()


