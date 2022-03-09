from datetime import datetime
from datetime import timedelta
from ColourText import format_text
import json
import os


class Projects:
    def __init__(self):
        self.__dict = {}
        self.__load_json()

    def __str__(self):
        return str(self.__dict)

    def __len__(self):
        return len(self.__dict)

    def get_keys(self):
        return list(self.__dict.keys())

    def get_project(self, name: str):
        return dict(self.__dict[name])

    def __create_project(self, name: str, sub_names=None):
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

    def update_project(self, session_out: tuple, name: str, sub_names=None):
        if name not in self.__dict:
            self.__create_project(name, sub_names)

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
                        time_spent = time_spent.strftime("%Mm %Ss")

                        sub_projects = [f"[_text256_26_]{sub_proj}[reset]" for sub_proj in session['Sub-Projects']]

                        print_output += format_text(f"[cyan]{session['Start Time']}[reset] to "
                                                    f"[cyan]{session['End Time']}[reset] \t"
                                                    f"{time_spent}  "
                                                    f"{project} {sub_projects} "
                                                    f" -> [yellow]{session['Note']}[reset]\n")

            if print_output != "":
                print_date = datetime.strptime(date, "%m-%d-%Y")
                print_date = print_date.strftime("%A %d %B %Y")
                day_total = str(timedelta(minutes=day_total)).split(".")[0]
                day_total = datetime.strptime(day_total, "%H:%M:%S")

                print(format_text(f"[underline]{print_date}[reset]"
                                  f" [_text256_77_]({day_total.strftime('%Mm %Ss')})[reset]"))
                print(print_output)

    def aggregate(self):
        self.log('all', 1)

    def __save_to_dict(self, prjct_dict: dict):
        name = list(prjct_dict.keys())[0]
        self.__dict[name] = prjct_dict[name]

    def save_to_json(self):
        prjct_json = json.dumps(self.__dict, indent=4)
        with open("projects.json", "w") as json_writer:
            json_writer.write(prjct_json)

    def __load_json(self):
        try:
            projects = open("projects.json", "r").read()
            self.__dict = json.loads(projects)
        except FileNotFoundError:
            open("projects.json", "w")
        except json.decoder.JSONDecodeError:
            pass


def main():
    os.system("cls")
    project_dict = Projects()
    """timer = Timer('Test', [])
    project_dict.update_project(timer.run_timer(), 'Test')
    project_dict.save_to_json()
    print(project_dict)"""

    project_dict.log()


if __name__ == "__main__":
    main()
