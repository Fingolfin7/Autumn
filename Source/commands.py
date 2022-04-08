import os
from charts import showBarGraphs, showPieChart
from timer import Timer
from projects import Projects
from ColourText import format_text

project_dict = Projects()
timer_list = []
name_lookup = {}


def parse_command(in_str: str):
    in_str = in_str.strip()
    str_parts = in_str.split(' ')
    func_args = [arg.strip() for arg in " ".join(str_parts[1:]).split(',')]

    if func_args.__contains__(""):
        func_args.remove("")

    return str_parts[0], func_args


def get_index(list_args):
    global timer_list
    global name_lookup
    if len(list_args) == 0:
        return None

    try:
        index = int(list_args[0])
    except ValueError:
        proj_name = list_args[0]
        sub_projs = list_args[1:]
        lookup = f"{proj_name} {sub_projs}"
        if lookup in name_lookup:
            index = name_lookup[lookup]
        else:
            index = None

    if index >= len(timer_list):
        index = None

    return index


def get_lookup_list(): return list(name_lookup)


def start_command(list_args):
    global project_dict
    global timer_list

    proj_name = list_args[0]
    sub_projs = list_args[1:]

    timer = Timer(proj_name, sub_projs)

    timer_list.append(timer)
    name_lookup[f"{proj_name} {sub_projs}"] = len(timer_list) - 1

    timer_list[-1].start()


def status_command(list_args):
    global timer_list

    if len(timer_list) == 0:
        print("No running projects.")
        return

    if len(list_args) > 0 and list_args[0] != 'all':
        i = get_index(list_args)
        if i is None:
            print(f"Invalid identifier!\nValid keys: {get_lookup_list()}"
                  f"\nValid indexes 0 -> {len(timer_list) - 1}")
            return
        timer_list[i].time_spent()

    else:
        for i in range(len(timer_list)):
            print(f"[{i}]: ", end="")
            timer_list[i].time_spent()


def stop_command(list_args):
    global project_dict
    global timer_list

    if len(timer_list) == 0:
        print("No running projects.")
        return

    if len(list_args) > 0:
        i = get_index(list_args)
        if i is None:
            print(f"Invalid key!\nValid keys: {get_lookup_list()}")
            return
        timer = timer_list[i]
    else:
        timer = timer_list[-1]

    project_dict.update_project(timer.stop(), timer.proj_name, timer.sub_projs)
    timer_list.remove(timer)


def list_projects():
    global project_dict
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


def list_subs(list_args):
    global project_dict
    project = list_args[0]

    if project not in project_dict.get_keys():
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


def show_totals(list_args):
    global project_dict

    if len(list_args) == 0:
        project_dict.get_totals()
    elif list_args[0].lower() == 'all':
        project_dict.get_totals()
    else:
        project_dict.get_totals(list_args)


def list_cmds():
    from Autumn import commands
    keys = sorted(commands.keys(), key=lambda x: x.lower())
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
    exit(0)


def delete_project(list_args):
    global project_dict
    project = list_args[0]

    x = input(format_text(f"Are you sure you want to delete [yellow]{project}[reset]? \n[Y/N]: "))
    if x == "Y" or x == "y":
        project_dict.delete_project(project)
        print(format_text(f"Deleted project [yellow]{project}[reset]"))


def export(list_args):
    global project_dict

    if list_args[0].lower() == 'all':
        projects = project_dict.get_keys()
    else:
        projects = list_args[: -1]

    filename = list_args[-1]

    if not filename.endswith(".json"):
        filename += ".json"

    x = input(format_text(f"Are you sure you want to export [yellow]{projects}[reset] to file '{filename}'?\n[Y/N]: "))

    if x == "Y" or x == "y":
        for project in projects:
            project_dict.export_project(project, filename)

        print(format_text(f"Exported [yellow]{projects}[reset] to '{filename}'"))


def import_exported(list_args):
    global project_dict

    if list_args[0].lower() == 'all':
        projects = []
    else:
        projects = list_args[: -1]

    filename = list_args[-1]

    if not filename.endswith(".json"):
        filename += ".json"

    x = input(format_text(f"Are you sure you want to import [yellow]{projects}[reset]"
                          f" from file '{filename}'?\n[Y/N]: "))

    if x == "Y" or x == "y":
        for project in projects:
            project_dict.load_exported(filename, project)

        print(format_text(f"Imported [yellow]{projects}[reset] from '{filename}'"))


def print_project(list_args):
    global project_dict
    project = list_args[0]

    project_dict.print_json_project(project)


def get_logs(list_args):
    global project_dict

    if len(list_args) == 0:
        project_dict.log()
        return

    try:
        if list_args[0].lower() == 'all':
            projects = 'all'
        else:
            projects = list_args[: -1]

        period = int(list_args[-1])
        project_dict.log(projects, period)
    except ValueError:
        if list_args[0].lower() == 'all':
            projects = 'all'
            project_dict.log(projects)
        else:
            project_dict.log(list_args)


def get_aggregate():
    global project_dict
    project_dict.aggregate()


def clr():
    os.system("cls")


def chart(list_args):
    global project_dict
    keys = project_dict.get_keys()
    chart_objects = list_args[0: -1]
    chart_type = str(list_args[-1:][0]).lower()

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
