import os
import json
from timer import td_str
from datetime import datetime
from datetime import timedelta
from config import get_base_path
from functions import listOfDates
from ColourText import format_text
from compress_json import json_unzip, json_zip, ZIPJSON_KEY


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

        # run a backup at the end of every month

        # if the year is not the same as the year from the last save date,
        # save all the projects of the last year to an archives file
        last_save_date = self.__last_save_date()
        if last_save_date.year != datetime.today().year:
            archive_dir = os.path.join(get_base_path(), "Archives")
            archive_file = os.path.join(archive_dir, f"Projects-{last_save_date.year}.json")

            if not os.path.isdir(archive_dir):
                os.mkdir(archive_dir)

            if not os.path.exists(archive_file):
                prjct_json = json.dumps(self.__dict, indent=4)
                with open(archive_file, "w") as json_writer:
                    json_writer.write(prjct_json)

                # empty dict and save
                self.__dict.clear()
                self.__save()

            print(f"Archived {last_save_date.year} projects to "
                  f"'Projects-{last_save_date.year}.json' in the Archives directory ({archive_dir}).")

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
        dates = [datetime.strptime(self.__dict[project]['Last Updated'], "%m-%d-%Y") for project in self.__dict]
        dates.sort()

        if len(dates) == 0:
            return datetime.today()

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

        # proj_data = self.get_project(name)
        # self.delete_project(name)
        self.__dict[new_name] = self.__dict.pop(name)
        self.__save()

    def rename_subproject(self, name: str, sub_name: str, new_sub_name: str):
        """
        Rename existing subproject
        """
        if name not in self.__dict:
            print(f"Invalid project name! '{name}' does not exist!")
            return

        if sub_name not in self.__dict[name]['Sub Projects']:
            print(f"Invalid subproject name! '{sub_name}' does not exist!")
            return

        # rename 'Sub Projects' keys
        if new_sub_name in self.__dict[name]['Sub Projects']:
            print(f"Subproject name '{new_sub_name}' already exists, merging subprojects...")
            # merge the subprojects
            self.__dict[name]['Sub Projects'][new_sub_name] += self.__dict[name]['Sub Projects'].pop(sub_name)
        else:
            self.__dict[name]['Sub Projects'][new_sub_name] = self.__dict[name]['Sub Projects'].pop(sub_name)

        # rename all the subproject entries in the session history
        for index in range(len(self.__dict[name]['Session History'])):
            self.__dict[name]['Session History'][index]['Sub-Projects'] = \
                [new_sub_name if x == sub_name else x for x in
                 self.__dict[name]['Session History'][index]['Sub-Projects']]

        self.__save()

    def remove_subproject(self, name, sub_name):
        project = self.get_project(name)
        if sub_name not in project['Sub Projects']:
            print(f"Invalid subproject name! '{sub_name}' does not exist!")
            return

        old_total_time = project['Total Time']

        # remove session history entries with the subproject IF the subproject is the only one in the entry
        for session in project['Session History']:
            if len(session['Sub-Projects']) == 1 and sub_name in session['Sub-Projects']:
                project['Session History'].remove(session)
            # otherwise, remove the subproject from the entry
            elif len(session['Sub-Projects']) > 1 and sub_name in session['Sub-Projects']:
                session['Sub-Projects'].remove(sub_name)
            else:  # do nothing
                pass

        # update the total time
        project['Total Time'] = 0
        for session in project['Session History']:
            project['Total Time'] += float(session['Duration'])

        project['Total Time'] = round(project['Total Time'], 2)

        # remove the subproject from the project dict
        project['Sub Projects'].pop(sub_name)

        print(format_text(f"Removed subproject [_text256_26_]{sub_name}[reset] from project [bright red]{name}[reset]"))
        print(format_text(f"Total time for project [bright red]{name}[reset] is now "
                          f"[_text256_34_]{round(project['Total Time']/60, 2)} hours[reset], "
                          f"from [_text256_34_]{round(old_total_time/60, 2)} hours[reset]"))
        # update and save dict
        self.__dict[name] = project
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

        :param start_time: session start time format: "MM-DD-YYYY HH:MM" if MM-DD-YYYY
        is not specified, track for the current day

        :param end_time: session end time format: "MM-DD-YYYY HH:MM" if MM-DD-YYYY
        is not specified, track for the current day

        :param project: project name
        :param sub_projects: session subprojects
        :param session_note: session note
        """

        def check_date(time):
            # check if date is specified in the time string, if not set it to today
            if len(time.split(" ")) == 1:  # if only time is specified
                time = datetime.strptime(time, '%H:%M')
                time = time.replace(year=datetime.today().year, month=datetime.today().month, day=datetime.today().day)
                return time
            else:
                return datetime.strptime(time, '%m-%d-%Y %H:%M')

        def check_year(time):
            time = check_date(time)
            if time.year != datetime.today().year:
                print(format_text(f"Year entered as [cyan]{time.year}[reset]. "
                                  f"Did you mean [cyan]{datetime.today().year}[reset]?"))
                confirm = input("[Y/N]: ")
                if confirm.lower() == 'y':
                    time = time.replace(year=datetime.today().year)
            return time

        start_time = check_year(start_time.strip())
        end_time = check_year(end_time.strip())

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

        if duration < 0:
            print(format_text(f"Invalid session time. End time cannot be before start time."))
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
                          f"[_text256_34_]({duration})[reset]"), end="")

        print(format_text(f" -> [yellow]{session_note}[reset]" if session_note != "" else ""))

    def merge(self, project1: dict, project2: dict, new_name: str):
        try:
            # get all the keys from both projects and initially set them to 0
            subs = {**project1['Sub Projects'], **project2['Sub Projects']}
            new_subs = {}
            for key in subs:
                new_subs[key] = 0.0

            merged_project = {
                'Start Date': project1['Start Date'] if
                datetime.strptime(project1['Start Date'], '%m-%d-%Y') < datetime.strptime(project2['Start Date'],
                                                                                          '%m-%d-%Y')
                else project2['Start Date'],

                'Last Updated': project1['Last Updated'] if
                datetime.strptime(project1['Last Updated'], '%m-%d-%Y') > datetime.strptime(project2['Last Updated'],
                                                                                            '%m-%d-%Y')
                else project2['Last Updated'],

                "Status": project1['Status'],

                "Total Time": 0.0,

                "Sub Projects": new_subs,

                "Session History": sorted(
                    [  # combine session histories and sort by date
                        *project1['Session History'],
                        *project2['Session History']
                    ],
                    # sort array by date and end time
                    key=lambda x: (datetime.strptime(x['Date'], '%m-%d-%Y'),
                                   datetime.strptime(x["End Time"], "%H:%M:%S")
                                   )
                ),
            }

            merged_project = self.__remove_duplicate_sessions(merged_project)

            self.__dict[new_name] = merged_project
            self.__save()
        except Exception as e:
            print(f"An error occurred when trying to merge: {e}")

    def backup(self):
        """
        Creates a backup of the projects file.
        :return: path to the backup file or False if an error occurred
        """

        backup_dir = os.path.join(get_base_path(), "Backups")

        if not os.path.exists(backup_dir):
            os.mkdir(backup_dir)

        backup_path = os.path.join(backup_dir, f"backup-{self.__last_save_date().strftime('%m-%d-%Y')}.json")
        try:
            with open(backup_path, 'w') as f:
                f.write(json.dumps(self.__dict, indent=4))
            return backup_path
        except Exception as e:
            print(f"An error occurred when trying to create a backup projects: {e}")
            return False

    def restore_backup(self, backup_path):
        """
        Restores the projects file from a backup. Overwrites the current projects file.
        :param backup_path:
        :return:  True if the backup was restored successfully, False if an error occurred
        """

        # check if the backup file exists
        if not os.path.exists(backup_path):
            print(f"Backup file does not exist: {backup_path}")
            return False

        # load the backup file
        with open(backup_path, 'r') as f:
            backup = json.load(f)
            # check if the backup is compressed and decompress it if it is
            if ZIPJSON_KEY in backup:
                backup = json_unzip(backup)

            self.__dict = backup  # overwrite the current projects file with the backup
            self.__save()
            return True

    # method to sync projects with a remote server or local file
    def sync(self, filepath):
        """
        Sync projects with a local file. Projects from both files will be merged and both files will be updated.
        :param filepath: the path to the remote file (a .json file)
        :return: True if the sync was successful, False if an error occurred
        """
        # check if the path is accessible
        try:
            if not os.path.exists(filepath):
                if not os.path.isdir(os.path.dirname(filepath)):
                    os.makedirs(os.path.dirname(filepath))
                with open(filepath, 'w'):
                    pass

            with open(filepath, 'r'):
                pass
        except Exception as e:
            print(f"An error occurred when trying to access the remote file: {e}")
            return False

        print(f"Syncing projects with file: {filepath}")

        # backup current projects
        backup_path = self.backup()
        if backup_path:
            print(f"Backup created: {backup_path}")
        else:
            print("Failed to create backup! Sync aborted!")
            return False

        is_compressed = False

        # get the data from the remote file
        try:
            with open(filepath, 'r') as f:
                remote_data = {}
                if os.stat(filepath).st_size != 0:  # if the file is not empty, load the data
                    remote_data = json.load(f)
                    is_compressed = ZIPJSON_KEY in remote_data
                    # check if remote file is compressed and unzip it if so
                    if is_compressed:
                        remote_data = json_unzip(remote_data)
        except Exception as e:
            print(f"An error occurred when trying to open the remote file: {e}")
            return False

        # use the merge method to merge the remote projects with the local projects
        for project in {**self.__dict, **remote_data}:  # combine the project keys of both dicts
            if project in self.get_keys() and project in remote_data.keys():
                self.merge(self.__dict[project], remote_data[project],
                           project)  # the project have the same name, so they will be merged into one project
                print(format_text(f"[yellow]{project}[reset] already exists, merging..."))
            elif project not in remote_data.keys():
                print(format_text(f"[green]{project}[reset] not found in remote file, adding..."))
            else:
                self.__dict[project] = remote_data[project]  # otherwise just add the project to the local projects
                print(format_text(f"[green]{project}[reset] added to projects"))

        # save the local projects
        self.__save()

        # update remote file
        try:
            with open(filepath, 'w') as f:
                # compress the data before writing it to the file if the file was originally compressed
                if is_compressed:
                    f.write(json.dumps(json_zip(self.__dict)))
                else:  # otherwise just write the data to the file
                    f.write(json.dumps(self.__dict, indent=4))
        except Exception as e:
            print(f"An error occurred when trying to update the remote file: {e}")
            return False

        print(f"Sync successful!")
        return True

    @staticmethod
    def __remove_duplicate_sessions(project: dict):
        """
        Private method that removes duplicate sessions from a project.
        Duplicate sessions are sessions with the same name, date, start-time, end-time, and duration.
        :param project: name of the project to remove duplicates from
        """
        if not project:
            return

        project['Total Time'] = 0
        for sub in project['Sub Projects']:
            project['Sub Projects'][sub] = 0

        seen = set()  # use a set to keep track of unique sessions
        new_session_history = []  # create a new session history

        for session in project['Session History']:
            # create a tuple with the values of the keys used to determine uniqueness
            key = (session['Date'], session['Start Time'], session['End Time'], tuple(session['Sub-Projects']))
            if key not in seen:  # if the tuple is not in the set, add it and add the session to the new session history
                seen.add(key)
                new_session_history.append(session)

        project['Session History'] = new_session_history  # set the new session history

        # sum up total time from session histories
        for session in project['Session History']:
            project['Total Time'] += float(session['Duration'])
            for sub in project['Sub Projects']:
                if sub in session['Sub-Projects']:
                    project['Sub Projects'][sub] += round(float(session['Duration']))

        project['Total Time'] = round(project['Total Time'], 2)
        return project  # update the project in the projects dict

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

        # Sort session_list by date
        session_list.sort(key=lambda x: datetime.strptime(x[1]['Date'], "%m-%d-%Y"))

        def format_time(time):
            if time.hour > 0:
                time = time.strftime("%Hh %Mm")
            else:
                time = time.strftime("%Mm %Ss")
            return time

        def truncate_note(nte, nteLength):
            if len(nte) > nteLength:
                nte = nte[0: nte.find(" ")] + "[red].[green].[blue].[yellow] " + nte[nte.rfind(" "):]
                # differentiate truncations from normal ellipses by adding color (RGB)
            return nte

        # Initialize variables
        current_date = None
        print_output = ""
        day_total = 0.0

        def print_date_output(crrnt_date, d_total):
            print_date = datetime.strptime(crrnt_date, "%m-%d-%Y")
            print_date = print_date.strftime("%A %d %B %Y")
            d_total = str(timedelta(minutes=d_total)).split(".")[0]
            d_total = datetime.strptime(d_total, "%H:%M:%S")
            d_total = format_time(d_total)

            print(format_text(f"[underline]{print_date}[reset]"
                              f" [_text256_34_]({d_total})[reset]"))

        # Iterate over sessions
        for project, session in reversed(session_list):
            # Check if date has changed
            if current_date != session['Date']:
                # Print output for previous date
                if current_date is not None:
                    print_date_output(current_date, day_total)
                    print(print_output)

                # Reset variables for new date
                current_date = session['Date']
                print_output = ""
                day_total = 0.0

            # Calculate time spent and add to day total
            time_spent = str(timedelta(minutes=session['Duration'])).split(".")[0]
            time_spent = datetime.strptime(time_spent, "%H:%M:%S")
            day_total += session['Duration']
            time_spent = format_time(time_spent)

            # Format subprojects and note
            sub_projects = [f"[_text256_26_]{sub_proj}[reset]" for sub_proj in session['Sub-Projects']]
            note = truncate_note(session['Note'], noteLength)

            # Add session details to print output
            print_output += format_text(f"[cyan]{session['Start Time']}[reset] to "
                                        f"[cyan]{session['End Time']}[reset] \t"
                                        f"{time_spent}  "
                                        f"[bright red]{project}[reset] "
                                        f"{sub_projects} " +
                                        (f" -> [yellow]{note}[reset]\n" if note != "" and sessionNotes else "\n")
                                        )

        # Print output for last date
        if current_date is not None:
            print_date_output(current_date, day_total)
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
            sess_count = len(self.__dict[prj]["Session History"])
            if sess_count > 0:
                print(format_text(f"*[_text256]Session Count: {sess_count}[reset]\n"
                                  f"*[_text256]Average duration: {td_str(td / sess_count)}[reset]", 66))
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
        """
        Sort the dictionary by key (project name) in alphabetical order.
        Also call __remove_duplicate_sessions() to remove duplicate sessions when sorting.
        :return:
        """
        sorted_keys = sorted(self.get_keys(), key=lambda x: x.lower())
        sorted_dict = {}

        for key in sorted_keys:
            # also remove duplicate sessions when sorting
            sorted_dict[key] = self.__remove_duplicate_sessions(self.__dict[key])

        self.__dict = sorted_dict

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
                            print(format_text(f"[yellow]{itr + 1}.{name}[reset]"))

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
