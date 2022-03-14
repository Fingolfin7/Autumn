import os
import random
from charts import showBarGraphs, showPieChart
from timer import Timer
from projects import Projects
from ColourText import format_text

project_dict = Projects()


def parse_command(in_str: str):
    in_str = in_str.strip()
    str_parts = in_str.split(' ')
    # print(str_parts)
    return str_parts[0], str_parts[1:]


def start_command(list_args):
    global project_dict

    proj_name = list_args[0]
    sub_projs = list_args[1:]

    timer = Timer(proj_name, sub_projs)
    project_dict.update_project(timer.run_timer(), proj_name, sub_projs)


def list_projects():
    global project_dict
    projects = project_dict.get_keys()
    print("Active Projects: ")

    length = len(projects)

    for i in range(length):
        colour = random.choice(['bright green', 'cyan', '_text256_26_'])
        output = format_text(f"[{colour}]{projects[i]}[reset], ")
        if i == length - 1:
            output = format_text(f"[{colour}]{projects[i]}[reset]")

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
    print(f"{project} sub-projects: ")

    for i in range(length):
        colour = random.choice(['bright green', 'cyan', '_text256_26_'])
        output = format_text(f"[{colour}]{sub_projects[i]}[reset], ")
        if i == length - 1:
            output = format_text(f"[{colour}]{sub_projects[i]}[reset]")

        print("", end=output)

        if (i + 1) % 5 == 0:
            print()

    print()


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
