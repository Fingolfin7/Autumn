# Autumn

> [!WARNING]  
> This directory contains the **Legacy** version of Autumn. This implementation operates on local JSON files and is no longer the primary development focus.

For the modern version of Autumn that connects to **AutumnWeb** via API, please use the CLI found in the `cli/` directory.

---

CLI Time Tracking software inspired by [Watson](https://github.com/TailorDev/Watson) that allows the user to track the amount of time they spend working on a given activity. 
Autumn allows users to create `projects` which can have sub activities or `subprojects`.
Projects are stored in a .json file called `projects.json`

## Setup
Here is a possible text for your readme file using the keywords you provided:

To set up my command line app and add it to the system or user PATH on windows, follow these steps:

Download or clone the repo using git and install the requirements using:

        `pip install -r requirements.txt`

Add the `Autumn\Source` directory to your system PATH or user PATH variable. This will allow you to use autumn from any terminal without specifying the full path. 
To do this, you can use the `setx` command in an elevated command prompt or edit the environment variables from the system settings.

For example, to add the directory to the user PATH variable using `setx`, you can run:

`setx path "%PATH%;C:\...\Autumn\Source"`

To add it to the system PATH variable (for all users), you can run:

`setx /M path "%PATH%;C:\...\Autumn\Source"`

Add `.PY` to your PATHEXT variable. This will allow you to run Python scripts without typing the `.py` extension. You can also use `setx` or edit the environment variables for this step.

For example, to add `.PY` to the user PATHEXT variable using `setx`, you can run:

`setx pathext "%PATHEXT%;.PY"`

To add it to the system PATHEXT variable (for all users), you can run:

`setx /M pathext "%PATHEXT%;.PY"`

Restart your terminal or open a new one to apply the changes. You should be able to use autumn as a command from any directory.

## Usage

To use Autumn, you can run the command `Autumn` or `Autumn.py` (not case sensitive) from any directory like so:


`AUTUMN COMMAND -h, --help [ARGS]`

For example:

`autumn start Mars -s Dragon Falcon "Falcon Heavy" Starship`

## Commands
Autumn has many commands including (use `autumn COMMAND -h, --help` for more info on a command):
- **start**: start a new timer
- **stop**: the current timer
- **status**: show the status of the current timer
- **track**: track a project for a given time period
- **remove**: remove a timer from the log
- **restart**: restart the current timer
- **projects**: list all projects and show `active`, `paused` and `complete` projects
- **subprojects**: list all subprojects for a given project
- **totals**: show the total time spent on a project and its subprojects
- **rename**: rename a project or subproject
- **delete**: delete a project
- **log**: show activity logs for the week or a given time period
- **mark**: mark a project as `active`, `paused` or `complete`
- **export**: export a project to a file in the `Autumn\Source\Exported` folder
- **import**: import a project from a file from the `Autumn\Source\Exported` folder
- **chart**: show a chart of the time spent on (a) project(s) choose between `bar`, `pie`, `heatmap`, `calendar`, and `scatter` charts
- **merge**: merge two projects
- **sync**: sync project data with a different file. You can specify a file with the `-f` flag or add a list of them (each location on a new line) in a `sync.txt` file
- **WatsonExport**: export a project to Watson
- **help**: show this help message


[//]: # (## Usage Examples)

[//]: # ()
[//]: # (### Windows Powershell &#40;renamed `args.py` to `Autumn.py`&#41;)

[//]: # ()
[//]: # (![Autumn2]&#40;https://user-images.githubusercontent.com/63872314/172476433-4be3a8d3-c3ef-4a17-b490-2cc1e1a56abb.gif&#41;)

