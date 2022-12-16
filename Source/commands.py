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

    project_status = project_dict.get_project(name)['Status']
    if project_status != "active":
        print(format_text(f"Cannot start a timer for a '[bright magenta]{project_status}[reset]' project."))
        return

    if name not in project_dict.get_keys():
        x = input(format_text(f"'[bright red]{name}[reset]' does not exist. Create it? \n[Y/N]: "))
        if x in ["Y", "y"]:
            project_dict.create_project(name, subprojects)
        else:
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
        print("No running projects.")
        return

    if index is None:
        print(f"Invalid identifier!\n"
              f"Valid indexes: 0 -> {len(timer_list) - 1}")
        print_timers()
        return

    timer = timer_list[index]

    timer.restart()
    save_pickles()


def status_command(index="all"):
    global timer_list

    if len(timer_list) == 0:
        print("No running projects.")
        return

    if index == 'all':
        for i in range(len(timer_list)):
            print(f"[{i}]: ", end="")
            timer_list[i].time_spent()
        return

    timer_list[int(index)].time_spent()


def remove_timer(index):
    global timer_list

    if len(timer_list) == 0:
        print("No running projects.")
        return

    if index is None:
        print(f"Invalid identifier!\n"
              f"Valid indexes: 0 -> {len(timer_list) - 1}\n")
        print_timers()
        return

    print(format_text(f"Removed timer: [bright red]{timer_list[index].proj_name}[reset]"))
    del timer_list[index]

    save_pickles()


def stop_command(index=-1):
    global project_dict
    global timer_list

    if len(timer_list) == 0:
        print("No running projects.")
        return

    timer = timer_list[index]

    project_dict.update_project(timer.stop(), timer.proj_name, timer.sub_projs)
    timer_list.remove(timer)
    save_pickles()


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
    """
    Track a session that wasn't recorded in real-time.

    :param start_time: session start time format: "MM-DD-YYY HH:MM"
    :param end_time: session end time format: "MM-DD-YYY HH:MM"
    :param project: project name
    :param sub_projects: session subprojects
    :param session_note: session note
    """
    global project_dict
    start_time = datetime.strptime(start_time, '%m-%d-%Y %H:%M')
    end_time = datetime.strptime(end_time, '%m-%d-%Y %H:%M')
    update_date = end_time.strftime("%m-%d-%Y")
    duration = end_time - start_time
    duration = duration.total_seconds() / 60

    project_status = project_dict.get_project(project)['Status']
    if project_status != "active":
        print(format_text(f"Cannot start a timer for a '[bright magenta]{project_status}[reset]' project."))
        return

    if project not in project_dict.get_keys():
        x = input(format_text(f"'[bright red]{project}[reset]' does not exist. Create it? \n[Y/N]: "))
        if x in ["Y", "y"]:
            project_dict.create_project(project, sub_projects)
        else:
            return

    for sub_proj in sub_projects:
        if sub_proj not in project_dict.get_project(project)['Sub Projects']:
            x = input(format_text(f"Sub-project '[_text256_26_]{sub_proj}[reset]' does not exist. "
                                  f"Create it? "
                                  f"\n[Y/N]: ")
                      )
            if x not in ["Y", "y"]:
                return

    project_dict.update_project((duration, session_note,
                                 start_time,
                                 end_time),
                                project, sub_projects, update_date)

    sub_projects = [f"[_text256_26_]{sub_proj}[reset]" for sub_proj in sub_projects]

    duration = str(timedelta(minutes=duration)).split('.')[0]
    duration = datetime.strptime(duration, "%H:%M:%S")
    if duration.hour > 0:
        duration = duration.strftime("%Hh %Mm")
    else:
        duration = duration.strftime("%Mm %Ss")

    print(format_text(f"Tracked [bright red]{project}[reset] "
                      f"{sub_projects} from [cyan]{start_time.strftime('%X')}[reset]"
                      f" to [cyan]{end_time.strftime('%X')}[reset] "
                      f"[_text256_34_]({duration})[reset]"
                      + f" -> [yellow]{session_note}[reset]" if session_note != "" else ""))


def list_projects():
    global project_dict
    projects = project_dict.get_keys()

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

    if not projects and not status:
        project_dict.get_totals()
    else:
        project_dict.get_totals(projects, status)


def list_cmds():
    commands = ["aggregate",  "chart", "clear", "delete", "export", "help", "import", "log",
                "mark", "projects", "quit", "remove", "rename", "restart", "start", "stop",
                "status", "subprojects", "totals", "track", "WatsonExport"]
    keys = sorted(commands, key=lambda x: x.lower())
    length = len(keys)

    print("Here are all the available commands:\n")

    for i in range(length):
        output = f"{keys[i]}, "
        if i == length - 1:
            output = f"{keys[i]}"

        print("", end=output)

        if (i + 1) % 3 == 0 and i != length - 1:
            print()

    print()


def quit_autumn():
    save_pickles()
    exit(0)


def mark_project_complete(name):
    global project_dict

    if name not in project_dict.get_keys():
        print(format_text(f"'[bright red]{name}[reset]' does not exist."))
        return

    project_dict.complete_project(name)
    print(format_text(f"Marked project [bright red]{name}[reset] as completed [bright green]:)[reset]"))


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

    if len(kwargs.keys()) == 0:
        project_dict.log()
        return

    project_dict.log(kwargs["projects"], kwargs["fromDate"], kwargs["toDate"], kwargs["status"])


def get_aggregate():
    global project_dict
    project_dict.aggregate()


def clr():
    os.system("cls")


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
        projects = keys
        if status:
            projects = [key for key in keys if project_dict.get_project(key)['Status'] == status]

    if len(projects) == 1:
        if projects[0] not in keys:
            print(f"Invalid project name! '{projects[0]}' does not exist!")
            return

        proj = project_dict.get_project(projects[0])
        for sub_proj in proj["Sub Projects"]:
            time_totals.append(proj["Sub Projects"][sub_proj] / 60)
            project_names.append(sub_proj)

    else:
        for name in projects:
            if name in keys:
                time_totals.append(project_dict.get_project(name)["Total Time"] / 60)
                project_names.append(name)
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
