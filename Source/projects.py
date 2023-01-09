import os
import json
from timer import td_str
from datetime import datetime
from datetime import timedelta
from config import get_base_path
from functions import listOfDates
from ColourText import format_text
from compress_json import json_unzip, json_zip


class Projects:
    def __init__(self, file="projects.json"):
        """
        :param file: filename to save and load project data from. File has to be located in the base directory
        """

        self.__dict = {}
        self.path = os.path.join(get_base_path(), file)
        self.exported_path = os.path.join(get_base_path(), "Exported")
        self.__status_tags = ["active", "paused", "complete"]

        self.__load()

        # if the year is not the same as the year from the last save date,
        # save all the projects of the last year to an archives file
        if self.__last_save_date().year != datetime.today().year:
            archive_dir = os.path.join(get_base_path(), "Archives")
            archive_file = os.path.join(archive_dir, f"Projects-{self.__last_save_date().year}.json")

            if not os.path.isdir(archive_dir):
                os.mkdir(archive_dir)

            if not os.path.exists(archive_file):
                prjct_json = json.dumps(self.__dict, indent=4)
                with open(archive_file, "w") as json_writer:
                    json_writer.write(prjct_json)

                # empty dict and save
                self.__dict.clear()
                self.__save()

            print(f"Archived {self.__last_save_date().year} projects to "
                  f"'Projects-{self.__last_save_date().year}.json' in the Archives directory ({archive_dir}).  ")

    def __str__(self):
        return str(self.__dict)

    def __len__(self):
        return len(self.__dict)

    def get_keys(self):
        """
        :return: a list of all the existing project names
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

    def __last_save_date(self):
        dates = [datetime.strptime(self.__dict[date]['Last Updated'], "%m-%d-%Y") for date in self.__dict]
        dates.sort()
        return dates[-1]

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
        :param sub_names: names of the project's subprojects if any.
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
                'Status': self.__status_tags[0],
                'Sub Projects': sub_projects,
                'Session History': []
            }
        self.__save()
        return True

    def update_project(self, session_out: tuple, name: str, sub_names=None,
                       update_date=datetime.today().strftime("%m-%d-%Y")):
        """
        Save project session history.

        :param session_out: a tuple with the session info including duration, session note, start and end time
        :param name: project to update
        :param sub_names: list of session subprojects
        :param update_date: date the project was tracked. set to current date by default.
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

        self.__dict[name]['Last Updated'] = update_date if \
            datetime.strptime(update_date, "%m-%d-%Y") > \
            datetime.strptime(self.__dict[name]['Last Updated'], "%m-%d-%Y") \
            else self.__dict[name]['Last Updated']

        history_log = {
            "Date": update_date,
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

    def track(self, start_time, end_time, project, sub_projects, session_note):
        """
        Track a session that wasn't recorded in real-time.

        :param start_time: session start time format: "MM-DD-YYY HH:MM"
        :param end_time: session end time format: "MM-DD-YYY HH:MM"
        :param project: project name
        :param sub_projects: session subprojects
        :param session_note: session note
        """
        start_time = datetime.strptime(start_time, '%m-%d-%Y %H:%M')
        if start_time.year != datetime.today().year:
            print(format_text(f"Start year entered as [cyan]{start_time.year}[reset]. "
                              f"Did you mean [cyan]{datetime.today().year}[reset]?"))
            x = input("[Y/N]: ")
            if x.lower() == 'y':
                start_time = start_time.replace(year=datetime.today().year)

        end_time = datetime.strptime(end_time, '%m-%d-%Y %H:%M')
        if end_time.year != datetime.today().year:
            print(format_text(f"End year entered as [cyan]{end_time.year}[reset]. "
                              f"Did you mean [cyan]{datetime.today().year}[reset]?"))
            x = input("[Y/N]: ")
            if x.lower() == 'y':
                end_time = end_time.replace(year=datetime.today().year)

        update_date = end_time.strftime("%m-%d-%Y")
        duration = end_time - start_time
        duration = duration.total_seconds() / 60

        if project not in self.__dict:
            x = input(format_text(f"'[bright red]{project}[reset]' does not exist. Create it? \n[Y/N]: "))
            if x in ["Y", "y"]:
                self.create_project(project, sub_projects)
            else:
                return

        project_status = self.__dict[project]['Status']
        if project_status != "active":
            print(format_text(f"Cannot start a timer for a '[bright magenta]{project_status}[reset]' project."))
            return

        for sub_proj in sub_projects:
            if sub_proj not in self.__dict[project]['Sub Projects']:
                x = input(format_text(f"Sub-project '[_text256_26_]{sub_proj}[reset]' does not exist. "
                                      f"Create it? "
                                      f"\n[Y/N]: ")
                          )
                if x not in ["Y", "y"]:
                    return

        self.update_project((duration, session_note, start_time, end_time), project, sub_projects, update_date)

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

    def log(self, projects="all", fromDate=None, toDate=None, status=None, sessionNotes=True, noteLength=300):
        """
        Print the session histories of projects over a given period.

        :param projects: list of project names to print session history.
        :param fromDate: date to start printing logs from in the format of MM-DD-YYY
        :param toDate: date to stop printing logs at in the format of MM-DD-YYY
        :param status: filter logged projects by status. Log either 'active', 'paused', or 'completed' projects
        :param sessionNotes: show session notes. True will print session notes, False will not.
        :param noteLength: maximum note length that can be printed before the note is replaced with an ellipse (...)
        """

        valid_projects = []
        keys = self.get_keys()

        if str(projects).lower() == 'all':
            valid_projects = keys
            if status and status in self.__status_tags:
                valid_projects = [key for key in keys if self.__dict[key]['Status'] == status]
        else:
            for prjct in projects:
                if prjct not in keys:
                    print(format_text(f"Invalid project name! '[bright red]{prjct}[reset]' does not exist!"))
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

                if len(note) > noteLength:
                    note = note[0: note.find(" ")] + "... " + note[note.rfind(" "):]

                print_output += format_text(f"[cyan]{session['Start Time']}[reset] to "
                                            f"[cyan]{session['End Time']}[reset] \t"
                                            f"{time_spent}  "
                                            f"[bright red]{project}[reset] "
                                            f"{sub_projects} " +
                                            (f" -> [yellow]{note}[reset]\n" if note != "" and sessionNotes else "\n")
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

    def get_totals(self, projects="all", status=None):
        """
        Print the time spent totals and subtotals for given projects.

        :param projects: list of project names to show time totals.
        :param status: filter logged projects by status. Log either 'active', 'paused', or 'completed' projects
        """
        valid_projects = []
        keys = self.get_keys()

        if str(projects).lower() == 'all':
            valid_projects = keys
            if status and status in self.__status_tags:
                valid_projects = [key for key in keys if self.__dict[key]['Status'] == status]
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

    def complete_project(self, name):
        """
        :param name: project name
        Mark a project as completed
        """

        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        self.__dict[name]["Status"] = self.__status_tags[2]
        self.__save()

    def pause_project(self, name):
        """
        :param name: project name
        Mark a project as paused
        """

        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        self.__dict[name]["Status"] = self.__status_tags[1]
        self.__save()

    def mark_project_active(self, name):
        """
        :param name: project name
        Mark a project as active
        """

        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        self.__dict[name]["Status"] = self.__status_tags[0]
        self.__save()

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

        try:
            # load and decompress json data
            self.__dict = json_unzip(json.loads(projects))
        except ...:
            # load an uncompressed file
            self.__dict = json.loads(projects)

        for project in self.__dict:
            if "Status" not in self.__dict[project]:
                self.__dict[project]["Status"] = self.__status_tags[0]

        self.__sort_dict()

    def export_project(self, name: str, filename: str):
        """
        Export projects to .json files.

        Files are saved in the 'Exported' folder within the base directory.
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
            if project_name != "" and project_name != "all":
                if project_name not in self.__dict.keys():
                    try:
                        self.__dict[project_name] = json.loads(projects)[project_name]
                        print(
                            format_text(f"Imported [yellow]{project_name}[reset] from '{filename}'"))
                    except KeyError:
                        print(format_text(f"\n[yellow]{project_name}[reset] cannot be found in '{path}'"))
                        print("Here are all the projects that were found: ")
                        for itr, name in enumerate(json.loads(projects)):
                            print(format_text(f"[yellow]{itr+1}.{name}[reset]"))

                else:
                    print(format_text(f"Conflict error! "
                                      f"Cannot import [yellow]{project_name}[reset] as it already exists!"))

            elif project_name == "all":
                temp_dict = json.loads(projects)
                for project in temp_dict:
                    if project not in self.__dict:
                        self.__dict[project] = temp_dict[project]
                        print(
                            format_text(f"Imported [yellow]{project}[reset] from '{filename}'"))
                    else:
                        print(format_text(f"Conflict error! "
                                          f"Cannot import [yellow]{project}[reset] as it already exists!"))
            self.__save()

        else:
            print(f"'{path}' does not exist!")
