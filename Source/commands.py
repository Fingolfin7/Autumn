import os
import _pickle as pickle
from config import get_base_path
from charts import *
from timer import Timer
from projects import Projects
from ColourText import format_text
from datetime import datetime, timedelta

project_dict = Projects()
timer_list = []
pickles_path = os.path.join(get_base_path(), 'active_timers.pkl')


def save_pickles():
    with open(pickles_path, 'wb') as output:
        pickle.dump(timer_list, output)


def load_pickles():
    global timer_list
    try:
        with open(pickles_path, 'rb') as inpt:
            timer_list = pickle.load(inpt)
    except FileNotFoundError:
        pass


def print_timers():
    for index in range(len(timer_list)):
        print(f"[{index}]: ", end="")
        timer_list[index].time_spent()


def start_command(name, subprojects):
    global project_dict
    global timer_list

    if name not in project_dict.get_keys():
        x = input(format_text(f"'[bright red]{name}[reset]' does not exist. Create it? \n[Y/N]: "))
        if x in ["Y", "y"]:
            project_dict.create_project(name, subprojects)
        else:
            return

    project_status = project_dict.get_project(name)['Status']
    if project_status != "active":
        print(format_text(f"Cannot start a timer for a '[bright magenta]{project_status}[reset]' project."))
        return

    for sub_proj in subprojects:
        if sub_proj not in project_dict.get_project(name)['Sub Projects']:
            x = input(format_text(f"Sub-project '[_text256_26_]{sub_proj}[reset]' does not exist. "
                                  f"Create it? "
                                  f"\n[Y/N]: ")
                      )
            if x not in ["Y", "y"]:
                return

    timer = Timer(name, subprojects)

    timer_list.append(timer)

    timer_list[-1].start()
    save_pickles()


def restart_command(index=-1):
    global project_dict
    global timer_list

    if len(timer_list) == 0:
        print("No running timers.")
        return

    try:
        timer = timer_list[index]
        timer.restart()
        save_pickles()
    except IndexError:
        print(f"Invalid identifier!\n"
              f"Valid indexes: 0 -> {len(timer_list) - 1}")
        print_timers()


def status_command(index="all"):
    global timer_list

    if len(timer_list) == 0:
        print("No running timers.")
        return

    if index == 'all':
        print_timers()
        return

    try:
        timer_list[int(index)].time_spent()
    except IndexError:
        print(f"Invalid identifier!\n"
              f"Valid indexes: 0 -> {len(timer_list) - 1}")
        print_timers()


def remove_timer(index):
    global timer_list

    if len(timer_list) == 0:
        print("No running timers.")
        return

    if not index:
        index = -1

    try:
        timer_name = timer_list[index].proj_name
        timer_list.pop(index)
        print(format_text(f"Removed timer: [bright red]{timer_name}[reset]"))
        save_pickles()
    except IndexError:
        print(f"Invalid identifier!\n"
              f"Valid indexes: 0 -> {len(timer_list) - 1}")
        print_timers()


def stop_command(index=-1):
    global project_dict
    global timer_list

    if len(timer_list) == 0:
        print("No running timers.")
        return
    try:
        timer = timer_list[index]

        if timer.proj_name not in project_dict.get_keys():
            x = input(format_text(f"'[bright red]{timer.proj_name}[reset]' does not exist. Create it? \n[Y/N]: "))
            if x in ["Y", "y"]:
                project_dict.create_project(timer.proj_name, timer.sub_projs)
            else:
                timer_list.remove(timer)
                save_pickles()
                return

        project_dict.update_project(timer.stop(), timer.proj_name, timer.sub_projs)
        timer_list.remove(timer)
        save_pickles()
    except IndexError:
        print(f"Invalid identifier!\n"
              f"Valid indexes: 0 -> {len(timer_list) - 1}")
        print_timers()


def export_to_watson(project_name):
    global project_dict
    if project_name not in project_dict.get_keys():
        print(format_text(f"'[bright red]{project_name}[reset]' does not exist."))
        return

    project = project_dict.get_project(project_name)

    for session in project['Session History']:
        date = datetime.strptime(session['Date'], "%m-%d-%Y")
        start_time = datetime.strptime(session["Start Time"], "%H:%M:%S")
        end_time = datetime.strptime(session["End Time"], "%H:%M:%S")
        duration = end_time - start_time
        duration = duration.total_seconds() / 60

        if duration < 0:
            start_date = (date - timedelta(days=1))
            start_time = datetime.strftime(start_date, "%Y-%m-%d") + " " + datetime.strftime(start_time, "%H:%M:%S")
            end_time = datetime.strftime(date, "%Y-%m-%d") + " " + datetime.strftime(end_time, "%H:%M:%S")
        else:
            start_time = datetime.strftime(date, "%Y-%m-%d") + " " + datetime.strftime(start_time, "%H:%M:%S")
            end_time = datetime.strftime(date, "%Y-%m-%d") + " " + datetime.strftime(end_time, "%H:%M:%S")

        trackWatson = f'watson add --from "{start_time}" --to "{end_time}" ' \
                      f'{project_name}'
        for sub_proj in session["Sub-Projects"]:
            trackWatson += f" + {sub_proj}"

        print(trackWatson)
        os.system(trackWatson)


def track_project(start_time, end_time, project, sub_projects, session_note):
    global project_dict
    project_dict.track(start_time, end_time, project, sub_projects, session_note)


def list_projects():
    global project_dict
    projects = project_dict.get_keys()

    if len(projects) == 0:
        print(format_text("No projects created. "
                          "You can create projects using the [bright green][italics]start[reset] command"))

    active_projects = [project for project in projects if project_dict.get_project(project)['Status'] == 'active']
    paused_projects = [project for project in projects if project_dict.get_project(project)['Status'] == 'paused']
    complete_projects = [project for project in projects if project_dict.get_project(project)['Status'] == 'complete']

    if len(complete_projects) > 0:
        print(format_text(f"[yellow][underline][italic]Complete:[reset] "))
        length = len(complete_projects)

        for i in range(length):
            output = f"{complete_projects[i]}, "
            if i == length - 1:
                output = f"{complete_projects[i]}"

            print("", end=output)

            if (i + 1) % 5 == 0:
                print()
        print("\n")

    if len(paused_projects) > 0:
        print(format_text(f"[magenta][underline][italic]Paused:[reset] "))
        length = len(paused_projects)

        for i in range(length):
            output = f"{paused_projects[i]}, "
            if i == length - 1:
                output = f"{paused_projects[i]}"

            print("", end=output)

            if (i + 1) % 5 == 0:
                print()
        print("\n")

    if len(active_projects) > 0:
        print(format_text(f"[underline][green][italic]Active:[reset] "))
        length = len(active_projects)

        for i in range(length):
            output = f"{active_projects[i]}, "
            if i == length - 1:
                output = f"{active_projects[i]}"

            print("", end=output)

            if (i + 1) % 5 == 0:
                print()
        print()


def list_subs(project: str):
    global project_dict

    if project not in project_dict.get_keys():
        print(format_text(f"'[bright red]{project}[reset]' does not exist."))
        return
    elif project == "":
        return

    sub_projects = list(project_dict.get_project(project)['Sub Projects'].keys())
    length = len(sub_projects)
    print(format_text(f"[underline]{project} sub-projects:[reset] "))

    for i in range(length):
        output = f"{sub_projects[i]}, "
        if i == length - 1:
            output = f"{sub_projects[i]}"

        print("", end=output)

        if (i + 1) % 5 == 0:
            print()

    print()


def show_totals(projects=None, status=None):
    global project_dict

    if len(project_dict) == 0:
        print(format_text("No projects created. "
                          "You can create projects using the [bright green][italics]start[reset] command"))

    if not projects and not status:
        project_dict.get_totals()
    else:
        project_dict.get_totals(projects, status)


def help():
    help_str = \
    "[underline][cyan]Here's a list of commands and their descriptions[reset] " \
    "(use `autumn COMMAND -h, --help` for more info on a command):\n"\
    "[bold][green]start[reset]: start a new timer\n"\
    "[bold][green]stop[reset]: stop the current timer\n"\
    "[bold][green]status[reset]: show the status of the current timer\n"\
    "[bold][green]track[reset]: track a project for a given time period\n"\
    "[bold][green]remove[reset]: remove a timer from the log\n"\
    "[bold][green]restart[reset]: restart the current timer\n"\
    "[bold][green]projects[reset]: list all projects and show `active`, `paused` and `complete` projects\n"\
    "[bold][green]subprojects[reset]: list all subprojects for a given project\n"\
    "[bold][green]totals[reset]: show the total time spent on a project and its subprojects\n"\
    "[bold][green]rename[reset]: rename a project or subproject\n"\
    "[bold][green]delete[reset]: delete a project\n"\
    "[bold][green]log[reset]: show activity logs for the week or a given time period\n"\
    "[bold][green]mark[reset]: mark a project as `active`, `paused` or `complete`\n"\
    "[bold][green]export[reset]: export a project to a file in the 'Exported' folder\n"\
    "[bold][green]import[reset]: import a project from a file from the 'Exported' folder\n"\
    "[bold][green]chart[reset]: show a chart of the time spent on (a) project(s) choose between bar, pie, and scatter charts\n"\
    "[bold][green]merge[reset]: merge two projects\n"\
    "[bold][green]WatsonExport[reset]: export a project to Watson\n"\
    "[bold][green]help[reset]: show this help message"
    print(format_text(help_str))


def quit_autumn():
    save_pickles()
    exit(0)


def mark_project_complete(name):
    global project_dict

    if name not in project_dict.get_keys():
        print(format_text(f"'[bright red]{name}[reset]' does not exist."))
        return

    project_dict.complete_project(name)
    # full list of emoji unicodes here: https://unicode.org/emoji/charts/full-emoji-list.html
    print(format_text(f"Marked project [bright red]{name}[reset] as completed \U0001F642"))


def mark_project_paused(name):
    global project_dict

    if name not in project_dict.get_keys():
        print(format_text(f"'[bright red]{name}[reset]' does not exist."))
        return

    project_dict.pause_project(name)
    print(format_text(f"Marked project [bright red]{name}[reset] as paused"))

def mark_project_active(name):
    global project_dict

    if name not in project_dict.get_keys():
        print(format_text(f"'[bright red]{name}[reset]' does not exist."))
        return

    project_dict.mark_project_active(name)
    print(format_text(f"Marked project [bright red]{name}[reset] as active"))

def rename_project(name: str, new_name: str):
    global project_dict

    if name not in project_dict.get_keys():
        print(format_text(f"'[bright red]{name}[reset]' does not exist."))
        return
    elif name == "":
        return

    x = input(format_text(f"Are you sure you want to rename [yellow]{name}[reset] to "
                          f"[yellow]{new_name}[reset]? \n[Y/N]: "))
    if x == "Y" or x == "y":
        project_dict.rename_project(name, new_name)
        print(format_text(f"Renamed project [yellow]{name}[reset] to [yellow]{new_name}[reset]"))

# rename subproject
def rename_subproject(project: str, subproject: str, new_sub_name: str):
    global project_dict

    if project not in project_dict.get_keys():
        print(format_text(f"'[bright red]{project}[reset]' does not exist."))
        return
    elif project == "":
        return

    x = input(format_text(f"Are you sure you want to rename subproject [_text256_26_]{subproject}[reset] to "
                          f"[_text256_26_]{new_sub_name}[reset]? \n[Y/N]: "))
    if x == "Y" or x == "y":
        project_dict.rename_subproject(project, subproject, new_sub_name)
        print(format_text(f"Renamed subproject [_text256_26_]{subproject}[reset] to [_text256_26_]{new_sub_name}[reset]"))

def delete_project(project: str):
    global project_dict

    if project not in project_dict.get_keys():
        print(format_text(f"'[bright red]{project}[reset]' does not exist."))
        return
    elif project == "":
        return

    x = input(format_text(f"Are you sure you want to delete [yellow]{project}[reset]? \n[Y/N]: "))
    if x == "Y" or x == "y":
        project_dict.delete_project(project)
        print(format_text(f"Deleted project [yellow]{project}[reset]"))

def merge_projects(first_project: str, second_project:str, new_name:str):
    global project_dict

    if first_project not in project_dict.get_keys():
        print(format_text(f"Invalid project name! '[bright red]{first_project}[reset]' does not exist!"))
        return
    if second_project not in project_dict.get_keys():
        print(format_text(f"Invalid project name! '[bright red]{second_project}[reset]' does not exist!"))
        return

    if new_name == "":
        print("Please specify a name for the merged project.")
        return

    x = input(format_text(f"Are you sure you want to merge [yellow]{first_project}[reset] and "
                          f"[yellow]{second_project}[reset]? \n[Y/N]: "))
    if x == "Y" or x == "y":
        project1 = project_dict.get_project(first_project)
        project2 = project_dict.get_project(second_project)

        project_dict.merge(project1, project2, new_name)
        print(format_text(f"Successfully merged [yellow]{first_project}[reset] and [yellow]{second_project}[reset] "
                          f"into [yellow]{new_name}[reset]"))

def sync_projects(file, is_remote:bool = False):
    global project_dict
    project_dict.sync(file, is_remote)



def export(projects: list, filename: str):
    global project_dict

    if not filename.endswith(".json"):
        filename += ".json"

    x = input(format_text(f"Are you sure you want to export [yellow]{projects}[reset] to file '{filename}'?\n[Y/N]: "))

    if x == "Y" or x == "y":
        for project in projects:
            project_dict.export_project(project, filename)

        print(format_text(f"Exported [yellow]{projects}[reset] to '{filename}'"))

def import_exported(projects: list, filename: str):
    global project_dict

    if not filename.endswith(".json"):
        filename += ".json"

    x = input(format_text(f"Are you sure you want to import [yellow]{projects if projects else 'everything'}[reset]"
                          f" from file '{filename}'?\n[Y/N]: "))

    if x == "Y" or x == "y":
        if not projects:
            project_dict.load_exported(filename, "all")
        for project in projects:
            project_dict.load_exported(filename, project)

        # print(format_text(f"Imported [yellow]{projects if projects else 'everything'}[reset] from '{filename}'"))

def print_project(project):
    global project_dict
    project_dict.print_json_project(project)

def get_logs(**kwargs):
    global project_dict

    if len(project_dict) == 0:
        print(format_text("No projects created. "
                          "You can create projects using the [bright green][italics]start[reset] command"))

    if len(kwargs.keys()) == 0:
        project_dict.log()
        return

    project_dict.log(kwargs["projects"], kwargs["fromDate"], kwargs["toDate"],
                     kwargs["status"], kwargs["sessionNote"], kwargs["noteLength"])

def chart(projects="all", chart_type="pie", status=None):
    global project_dict
    keys = project_dict.get_keys()

    chart_funcs = {
        'bar': showBarGraphs,
        'pie': showPieChart,
        'scatter': showScatterGraph
    }

    if chart_type not in chart_funcs:
        print(f"'{chart_type}' is not a valid chart type! "
              f"\nValid chart types: {list(chart_funcs.keys())}")
        return

    time_totals = []
    project_names = []
    names_and_hist = []

    if str(projects).lower() == "all":
        if status:
            projects = [key for key in keys if project_dict.get_project(key)['Status'] == status]
        else:
            projects = keys

    if len(projects) == 1:
        if projects[0] not in keys:
            print(f"Invalid project name! '{projects[0]}' does not exist!")
            return

        if chart_type == "scatter": # get the dates and durations for each subproject to show on the scatter graph
            proj = project_dict.get_project(projects[0])
            sess_hist = proj["Session History"]

            for sub_proj in proj["Sub Projects"]:
                dates = [datetime.strptime(sess['Date'], "%m-%d-%Y") for sess in sess_hist
                         if sub_proj in sess['Sub-Projects']]
                durations = [sess['Duration'] / 60 for sess in sess_hist
                             if sub_proj in sess['Sub-Projects']]
                project_names.append(sub_proj)
                names_and_hist.append((sub_proj, (dates, durations))) # append the subproject name, its dates, and durations

        else: # get the total time for each subproject to show on the pie or bar graph
            sess = project_dict.get_project(projects[0])
            for sub_proj in sess["Sub Projects"]:
                time_totals.append(sess["Sub Projects"][sub_proj] / 60)
                project_names.append(sub_proj)

    else:
        for name in projects:
            if name in keys and len(projects) > 1:
                time_totals.append(project_dict.get_project(name)["Total Time"] / 60)
                sess_hist = project_dict.get_project(name)["Session History"]
                dates = [datetime.strptime(sess['Date'], "%m-%d-%Y") for sess in sess_hist]
                durations = [sess['Duration'] / 60 for sess in sess_hist]
                names_and_hist.append((name, (dates, durations)))
            else:
                print(f"Invalid project name! '{name}' does not exist!")


    if chart_type == "scatter":
        print(f"Projects: {project_names}")
        chart_funcs[chart_type](names_and_hist)
    elif chart_type in ['bar', 'pie'] and len(time_totals) > 0:
        print(f"Projects: {project_names}")
        print(f"Times: {time_totals}")
        chart_funcs[chart_type](project_names, time_totals)
