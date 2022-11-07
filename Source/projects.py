import os
import json
import time
from timer import td_str
from datetime import datetime
from datetime import timedelta
from config import get_base_path
from ColourText import format_text
from compress_json import json_unzip, json_zip


def listOfDates(fromDate: str, toDate: str):
    fromDate = datetime.strptime(fromDate, "%m-%d-%Y") \
        if fromDate else datetime.today() - timedelta(days=7)
    toDate = datetime.strptime(toDate, "%m-%d-%Y") \
        if toDate else datetime.today()

    # TODO:  if the toDate is earlier than fromDate, and no fromDate is provided,
    #  set fromDate to the beginning of the current month

    # if fromDate > toDate and fromDate and not toDate

    if fromDate > toDate:
        return None

    return [(toDate + timedelta(days=-i)).strftime("%m-%d-%Y") for i in range((toDate - fromDate).days + 1)]


class Projects:
    def __init__(self, file="projects.json"):
        """
        :param file: filename to save and load project data from. File has to be located in the base directory
        """

        self.__dict = {}
        self.path = os.path.join(get_base_path(), file)
        self.exported_path = os.path.join(get_base_path(), "Exported")
        self.__load()

    def __str__(self):
        return str(self.__dict)

    def __len__(self):
        return len(self.__dict)

    def get_keys(self):
        """
        Return a list of all the existing project names
        """
        return list(self.__dict.keys())

    def get_project(self, name: str):
        """
        Return a project dictionary.
        :param name: existing project name
        :return: project dict object
        """
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        return self.__dict[name]

    def delete_project(self, name: str):
        """
        Delete an existing project
        """
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        self.__dict.pop(name)
        self.__save()

    def rename_project(self, name: str, new_name: str):
        """
        Rename existing project
        """
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        proj_data = self.get_project(name)
        self.delete_project(name)
        self.__dict[new_name] = proj_data
        self.__save()

    def print_json_project(self, name: str):
        project = self.get_project(name)
        print(json.dumps(project, indent=4))

    def create_project(self, name: str, sub_names=None):
        """
        Create a new project.

        :param name: project name
        :param sub_names: names of the project's sub-projects if any.
        """
        if name not in self.__dict:
            sub_projects = {}

            if sub_names is not None:
                for sub_name in sub_names:
                    sub_projects[sub_name] = 0.0

            self.__dict[name] = {
                'Start Date': datetime.today().strftime("%m-%d-%Y"),
                'Last Updated': datetime.today().strftime("%m-%d-%Y"),
                'Total Time': 0.0,
                'Sub Projects': sub_projects,
                'Session History': []
            }
        self.__save()
        return True

    def update_project(self, session_out: tuple, name: str, sub_names=None):
        """
        Save project session history.

        :param session_out: a tuple with the session info including duration, session note, start and end time
        :param name: project to update
        :param sub_names: list of session sub-projects
        """

        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        duration = session_out[0]
        session_note = session_out[1]

        if type(session_out[2]) is not datetime:
            start_time = datetime.fromtimestamp(session_out[2]).strftime('%X')
            end_time = datetime.fromtimestamp(session_out[3]).strftime('%X')
        else:
            start_time = session_out[2].strftime('%X')
            end_time = session_out[3].strftime('%X')

        total_time = float(self.__dict[name]['Total Time']) + duration
        self.__dict[name]['Total Time'] = round(total_time, 2)

        if sub_names is not None:
            sub_projects = dict(self.__dict[name]['Sub Projects'])

            for sub_name in sub_names:
                if sub_name in sub_projects:
                    total = float(sub_projects[sub_name])
                    sub_projects[sub_name] = round(total + duration, 2)
                else:
                    sub_projects[sub_name] = duration

            self.__dict[name]['Sub Projects'] = sub_projects

        today = datetime.today().strftime("%m-%d-%Y")

        self.__dict[name]['Last Updated'] = today

        history_log = {
            "Date": today,
            "Start Time": start_time,
            "End Time": end_time,
            "Sub-Projects": sub_names,
            "Duration": round(duration, 2),
            "Note": session_note
        }

        try:
            self.__dict[name]['Session History'].append(history_log)
        except KeyError:
            self.__dict[name]['Session History'] = [history_log]

        self.__save()

    def log(self, projects="all", fromDate=None, toDate=None):
        """
        Print the session histories of projects over a given period.

        :param projects: list of project names to print session history.
        :param fromDate: date to start printing logs from in the format of MM-DD-YYY
        :param toDate: date to stop printing logs at in the format of MM-DD-YYY

        """
        valid_projects = []
        keys = self.get_keys()

        if str(projects).lower() == 'all':
            valid_projects = keys
        else:
            for prjct in projects:
                if prjct not in keys:
                    print(f"Invalid project name! '{prjct}' does not exist!")
                else:
                    valid_projects.append(prjct)

        dates = listOfDates(fromDate, toDate)

        if not dates:
            print(format_text(f'Invalid input! End date [cyan]"{toDate}"[reset] cannot be earlier '
                              f'than start date [cyan]"{fromDate}"[reset].'))
            return

        # create a sessions list
        sessions_list = [(project, self.__dict[project]["Session History"]) for project in valid_projects]
        cleaned_sessions = []

        for project, session_list in sessions_list:
            for session in session_list:
                if session["Date"] in dates:
                    cleaned_sessions.append((project, session))

        # sort sessions list by end time
        session_list = sorted(cleaned_sessions, key=lambda x: datetime.strptime(x[1]["End Time"], "%H:%M:%S"))

        for date in dates:
            print_output = ""
            day_total = 0.0
            for project, session in session_list:
                if date != session['Date']:
                    continue
                time_spent = str(timedelta(minutes=session['Duration'])).split(".")[0]
                time_spent = datetime.strptime(time_spent, "%H:%M:%S")
                day_total += session['Duration']

                if time_spent.hour > 0:
                    time_spent = time_spent.strftime("%Hh %Mm")
                else:
                    time_spent = time_spent.strftime("%Mm %Ss")

                sub_projects = [f"[_text256_26_]{sub_proj}[reset]" for sub_proj in session['Sub-Projects']]

                note = session['Note']

                if len(note) > 300:
                    note = note[0: note.find(" ")] + "... " + note[note.rfind(" "):]

                print_output += format_text(f"[cyan]{session['Start Time']}[reset] to "
                                            f"[cyan]{session['End Time']}[reset] \t"
                                            f"{time_spent}  "
                                            f"[bright red]{project}[reset] "
                                            f"{sub_projects} " +
                                            (f" -> [yellow]{note}[reset]\n" if note != "" else "\n")
                                            )

            if print_output == "":
                continue

            print_date = datetime.strptime(date, "%m-%d-%Y")
            print_date = print_date.strftime("%A %d %B %Y")
            day_total = str(timedelta(minutes=day_total)).split(".")[0]
            day_total = datetime.strptime(day_total, "%H:%M:%S")

            if day_total.hour > 0:
                day_total = day_total.strftime('%Hh %Mm')
            else:
                day_total = day_total.strftime('%Mm %Ss')

            print(format_text(f"[underline]{print_date}[reset]"
                              f" [_text256_34_]({day_total})[reset]"))
            print(print_output)

    def aggregate(self):
        """
        Print the session histories of projects for the current day.
        """
        today = datetime.today().strftime("%m-%d-%Y")
        self.log("all", today, today)

    def get_totals(self, projects="all"):
        """
        Print the time spent totals and subtotals for given projects.

        :param projects: list of project names to show time totals.
        """
        valid_projects = []
        keys = self.get_keys()

        if str(projects).lower() == 'all':
            valid_projects = keys
        else:
            for prjct in projects:
                if prjct not in keys:
                    print(f"Invalid project name! '{prjct}' does not exist!")
                else:
                    valid_projects.append(prjct)

        for prj in valid_projects:
            td = timedelta(minutes=self.__dict[prj]['Total Time'])
            startDate = datetime.strptime(self.__dict[prj]['Start Date'], "%m-%d-%Y")
            endDate = datetime.strptime(self.__dict[prj]['Last Updated'], "%m-%d-%Y")
            startDate = startDate.strftime("%d %B %Y")
            endDate = endDate.strftime("%d %B %Y")
            print(format_text(f"[bright red]{prj}[reset]: [_text256_34_]{td_str(td)}[reset] "
                              f"([cyan]{startDate}[reset] -> [cyan]{endDate}[reset])"))

            sub_ls = list(self.__dict[prj]["Sub Projects"])
            length = len(sub_ls)

            for i in range(length):
                sub = sub_ls[i]
                sub_td = timedelta(minutes=self.__dict[prj]["Sub Projects"][sub])

                if i == 0 and length < 0 or i == length - 1:
                    print(format_text(f"└───[_text256_26_]{sub}[reset]: {td_str(sub_td)}"))
                else:
                    print(format_text(f"├───[_text256_26_]{sub}[reset]: {td_str(sub_td)}"))

            print("")

    def __sort_dict(self):
        sorted_keys = sorted(self.get_keys(), key=lambda x: x.lower())
        sorted_dict = {}

        for key in sorted_keys:
            sorted_dict[key] = self.__dict[key]

        self.__dict = sorted_dict

    def __save_to_dict(self, project: dict):
        name = list(project.keys())[0]
        self.__dict[name] = project[name]

    def __save(self):
        self.__sort_dict()
        # compress and dump json data
        prjct_json = json.dumps(json_zip(self.__dict))
        with open(self.path, "w") as json_writer:
            json_writer.write(prjct_json)

    def __load(self):
        if not os.path.exists(self.path):
            return
        projects = open(self.path, "r").read()
        # load and decompress json data
        self.__dict = json_unzip(json.loads(projects))
        self.__sort_dict()

    def export_project(self, name: str, filename: str):
        """
        Export projects to .json files.

        Files are saved in the 'Exported' folder within the project directory.
        Has to end in .json.
        If extension isn't added, it will be added by the function.

        :param name: name of existing project to be exported
        :param filename: filename to save project in.

        """
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        if not os.path.isdir(self.exported_path):
            os.mkdir(self.exported_path)

        path = os.path.join(self.exported_path, filename)

        if os.path.exists(path):
            file_contents = open(path, "r").read()
            file_dict = json.loads(file_contents)
        else:
            file_dict = {}

        file_dict[name] = self.__dict[name]

        prjct_json = json.dumps(file_dict, indent=4)

        with open(path, "w") as json_writer:
            json_writer.write(prjct_json)

        self.delete_project(name)

    def load_exported(self, filename: str, project_name=""):
        """
        Import previously exported projects.

        :param filename: filename to save project in.
        :param project_name: name of the project to import from the file

        """
        path = os.path.join(self.exported_path, filename)

        if os.path.exists(path):
            projects = open(path, "r").read()
            if project_name != "":
                self.__dict[project_name] = json.loads(projects)[project_name]
            else:
                self.__dict += json.loads(projects)
            self.__save()

        else:
            print(f"'{path}' does not exist!")
