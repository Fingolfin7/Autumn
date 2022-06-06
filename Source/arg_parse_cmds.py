import os
import _pickle as pickle
from charts import showBarGraphs, showPieChart
from timer import Timer
from projects import Projects
from ColourText import format_text

project_dict = Projects()
timer_list = []


def save_pickles():
    with open('active_timers.pkl', 'wb') as output:
        pickle.dump(timer_list, output)


def load_pickles():
    global timer_list
    try:
        with open('active_timers.pkl', 'rb') as inpt:
            timer_list = pickle.load(inpt)
    except FileNotFoundError:
        pass


def get_index(index_in):
    global timer_list

    try:
        index = int(index_in)
    except ValueError:
        return None

    if index >= len(timer_list):
        index = None

    return index


def print_timers():
    for index in range(len(timer_list)):
        print(f"[{index}]: ", end="")
        timer_list[index].time_spent()


def start_command(proj_name, sub_projs):
    global project_dict
    global timer_list

    if proj_name not in project_dict.get_keys():
        x = input(format_text(f"'[bright red]{proj_name}[reset]' does not exist. Create it? \n[Y/N]: "))
        if x in ["Y", "y"]:
            project_dict.create_project(proj_name, sub_projs)
        else:
            return

    for sub_proj in sub_projs:
        if sub_proj not in project_dict.get_project(proj_name)['Sub Projects']:
            x = input(format_text(f"Sub-project '[_text256_26_]{sub_proj}[reset]' does not exist. "
                                  f"Create it? "
                                  f"\n[Y/N]: ")
                      )
            if x not in ["Y", "y"]:
                return

    timer = Timer(proj_name, sub_projs)

    timer_list.append(timer)

    timer_list[-1].start()
    save_pickles()


def status_command(timer_index):
    if len(timer_list) == 0:
        print("No running projects.")
        return

    if timer_index not in ['all', None]:
        i = get_index(timer_index)
        if i is None:
            print(f"Invalid identifier!\n"
                  f"Valid indexes: 0 -> {len(timer_list) - 1}")
            print_timers()
            return
        timer_list[i].time_spent()
    else:
        print_timers()


def remove_timer(timer_index):
    global timer_list

    if len(timer_list) == 0:
        print("No running projects.")
        return
    if timer_index is None:
        print("No timer index selected!\n"
              f"Valid indexes: 0 -> {len(timer_list) - 1}")
        print_timers()
        return

    i = get_index(timer_index)
    if i is None:
        print(f"Invalid identifier!\n"
              f"Valid indexes: 0 -> {len(timer_list) - 1}")
        print_timers()
        return
    print(f"Removed timer: {timer_list[i].proj_name}")
    del timer_list[i]

    save_pickles()


def stop_command(timer_index):
    global project_dict
    global timer_list

    if len(timer_list) == 0:
        print("No running projects.")
        return

    if timer_index is not None:
        i = get_index(timer_index)
        if i is None:
            print(f"Invalid identifier!\n"
                  f"Valid indexes: 0 -> {len(timer_list) - 1}")
            print_timers()
            return
        timer = timer_list[i]
    else:
        timer = timer_list[-1]

    project_dict.update_project(timer.stop(), timer.proj_name, timer.sub_projs)
    timer_list.remove(timer)
    save_pickles()


def list_projects():
    projects = project_dict.get_keys()
    print(format_text(f"[underline]Projects:[reset] "))

    length = len(projects)

    for i in range(length):
        output = f"{projects[i]}, "
        if i == length - 1:
            output = f"{projects[i]}"

        print("", end=output)

        if (i + 1) % 5 == 0:
            print()

    print()


def list_subs(proj_name):
    if proj_name not in project_dict.get_keys():
        return

    sub_projects = list(project_dict.get_project(proj_name)['Sub Projects'].keys())
    length = len(sub_projects)
    print(format_text(f"[underline]{proj_name} sub-projects:[reset] "))

    for i in range(length):
        output = f"{sub_projects[i]}, "
        if i == length - 1:
            output = f"{sub_projects[i]}"

        print("", end=output)

        if (i + 1) % 5 == 0:
            print()

    print()


def show_totals(projs):
    global project_dict

    if projs is None or "all" in projs:
        project_dict.get_totals()
    else:
        project_dict.get_totals(projs)


def quit_autumn():
    save_pickles()
    exit(0)


def rename_project(name, new_name):
    global project_dict

    x = input(format_text(f"Are you sure you want to rename [yellow]{name}[reset] to "
                          f"[yellow]{new_name}[reset]? \n[Y/N]: "))
    if x == "Y" or x == "y":
        project_dict.rename_project(name, new_name)
        print(format_text(f"Renamed project [yellow]{name}[reset] to [yellow]{new_name}[reset]"))


def delete_project(proj_name):
    global project_dict

    if proj_name not in project_dict.get_keys():
        return

    x = input(format_text(f"Are you sure you want to delete [yellow]{proj_name}[reset]? \n[Y/N]: "))
    if x == "Y" or x == "y":
        project_dict.delete_project(proj_name)
        print(format_text(f"Deleted project [yellow]{proj_name}[reset]"))


def export(projects, filename):
    global project_dict

    if 'all' in projects:
        projects = project_dict.get_keys()

    if not filename.endswith(".json"):
        filename += ".json"

    x = input(format_text(f"Are you sure you want to export [yellow]{projects}[reset] to file '{filename}'?\n[Y/N]: "))

    if x.lower() == "y":
        for project in projects:
            project_dict.export_project(project, filename)

        print(format_text(f"Exported [yellow]{projects}[reset] to '{filename}'"))


def import_exported(projects, filename):
    global project_dict

    if not filename.endswith(".json"):
        filename += ".json"

    x = input(format_text(f"Are you sure you want to import [yellow]{projects}[reset]"
                          f" from file '{filename}'?\n[Y/N]: "))

    if x.lower() == "y":
        for project in projects:
            project_dict.load_exported(filename, project)

        print(format_text(f"Imported [yellow]{projects}[reset] from '{filename}'"))


def get_logs(projs, period=None):
    global project_dict

    if "all" in projs:
        if period is not None:
            project_dict.log(projs, period)
        else:
            project_dict.log()
        return
    else:
        if period is not None:
            project_dict.log(projs, period)
        else:
            project_dict.log(projs)
        return


def get_aggregate():
    global project_dict
    project_dict.aggregate()


def clr():
    os.system("cls")


def chart(projects, chart_type):
    global project_dict
    keys = project_dict.get_keys()
    chart_objects = projects
    chart_type = chart_type.lower()

    chart_funcs = {
        'bar': showBarGraphs,
        'pie': showPieChart
    }

    if chart_type not in chart_funcs:
        print(f"'{chart_type}' is not a valid chart type! "
              f"\nValid chart types: {list(chart_funcs.keys())}")
        return

    time_totals = []
    project_names = []

    if chart_objects[0].lower() == "all":
        chart_objects = keys

    if len(chart_objects) == 1:
        if chart_objects[0] not in keys:
            print(f"Invalid project name! '{chart_objects[0]}' does not exist!")
            return

        proj = project_dict.get_project(chart_objects[0])
        for sub_proj in proj["Sub Projects"]:
            time_totals.append(proj["Sub Projects"][sub_proj] / 60)
            project_names.append(sub_proj)

    else:
        for name in chart_objects:
            if name in keys:
                time_totals.append(project_dict.get_project(name)["Total Time"] / 60)
                project_names.append(name)
            else:
                print(f"Invalid project name! '{name}' does not exist!")

    if len(time_totals) > 0:
        print(f"Projects: {project_names}")
        print(f"Times: {time_totals}")
        chart_funcs[chart_type](project_names, time_totals)

