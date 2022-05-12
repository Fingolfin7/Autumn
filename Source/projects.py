from datetime import datetime
from datetime import timedelta
from ColourText import format_text
from timer import td_str
from compress_json import json_unzip, json_zip
import json
import os


class Projects:
    def __init__(self, path="projects.json"):
        self.__dict = {}
        self.path = path
        self.__load()

    def __str__(self):
        return str(self.__dict)

    def __len__(self):
        return len(self.__dict)

    def get_keys(self):
        return list(self.__dict.keys())

    def get_project(self, name: str):
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        return self.__dict[name]

    def delete_project(self, name: str):
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        self.__dict.pop(name)
        self.__save()

    def rename_project(self, name:str, new_name: str):
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
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        duration = session_out[0]
        session_note = session_out[1]
        start_time = datetime.fromtimestamp(session_out[2]).strftime('%X')
        end_time = datetime.fromtimestamp(session_out[3]).strftime('%X')

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

    def log(self, projects="all", days=7):
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

        dates = [(datetime.today() - timedelta(days=i)).strftime("%m-%d-%Y")
                 for i in range(days)]

        for date in dates:
            print_output = ""
            day_total = 0.0
            for project in valid_projects:
                for session in self.__dict[project]["Session History"]:
                    if date == session['Date']:
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
                                                    f"{sub_projects} "
                                                    f" -> [yellow]{note}[reset]\n")

            if print_output != "":
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
        self.log('all', 1)

    def get_totals(self, projects="all"):
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
            print(format_text(f"[bright red]{prj}[reset]: [_text256_34_]{td_str(td)}[reset]"))

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
        # prjct_json = json.dumps(self.__dict, indent=4)
        # compress and dump json data
        prjct_json = json.dumps(json_zip(self.__dict))
        with open(self.path, "w") as json_writer:
            json_writer.write(prjct_json)

    def __load(self):
        if not os.path.exists(self.path):
            print(f"Cannot find file '{self.path}'! Quitting.")
            exit(0)
            return
        projects = open(self.path, "r").read()
        # self.__dict = json.loads(projects)
        # load and decompress json data
        self.__dict = json_unzip(json.loads(projects))
        self.__sort_dict()

    def export_project(self, name: str, filename: str):
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        if not os.path.isdir("Exported"):
            os.mkdir("Exported")

        path = os.path.join("Exported", filename)

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
        path = os.path.join("Exported", filename)

        if os.path.exists(path):
            projects = open(path, "r").read()
            if project_name != "":
                self.__dict[project_name] = json.loads(projects)[project_name]
            else:
                self.__dict += json.loads(projects)
            self.__save()

        else:
            print(f"'{path}' does not exist!")


def main():
    os.system("")
    project_dict = Projects()
    """timer = Timer('Test', [])
    project_dict.update_project(timer.run_timer(), 'Test')
    print(project_dict)"""

    # project_dict.export_project("AAtest", "March-2022.json")
    # project_dict.load_exported("March-2022.json", "AAtest")
    # project_dict.print_json_project("AAtest")


if __name__ == "__main__":
    main()
