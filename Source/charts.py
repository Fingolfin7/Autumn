import matplotlib.pyplot as plt
from datetime import datetime
import seaborn as sns
import plotly.express as px
import pandas as pd


def showPieChart(names, totals):
    final_total = sum(totals)

    if final_total < 1:
        totals = [x * 60 for x in totals]  # move from hours back to minutes
        plt.pie(totals, labels=names, autopct="%1.1f%%")
    else:
        plt.pie(totals, labels=names, autopct="%1.1f%%")

    plt.title("Tracked Projects")
    plt.show()


def showBarGraphs(names, totals):
    plt.bar(names, totals, label="Total hours")
    plt.title("Tracked Projects")
    plt.xlabel("Projects")
    plt.ylabel("Time (in hours)")

    plt.legend()

    plt.show()


def showScatterGraph(name_and_hist):
    for name, hist in name_and_hist:
        plt.scatter(hist[0], hist[1], label=name)

    plt.title("Tracked Projects")
    plt.xlabel("Dates")
    plt.ylabel("Session Duration (in hours)")

    plt.legend()

    plt.show()


def showHeatMap(project_histories: list, title: str = "Projects Heatmap", annotate=False, accuracy: int = 0):
    data = []
    for session in project_histories:
        day = datetime.strptime(session["Date"], "%m-%d-%Y").strftime("%A")
        try:
            time = datetime.strptime(session["End Time"], "%H:%M").strftime("%H:%M")
        except ValueError:
            time = datetime.strptime(session["End Time"], "%H:%M:%S").strftime("%H:%M")
        duration = float(session["Duration"]) / 60
        data.append((day, time, duration))

    df = pd.DataFrame(columns=['Day', 'End Time', 'Duration'], data=data)

    # Group times into hourly buckets
    df['End Time'] = pd.to_datetime(df['End Time'], format='%H:%M')
    df['End Time'] = df['End Time'].dt.floor('H').dt.time

    # Use pd.Categorical to list days of the week in order
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df['Day'] = pd.Categorical(df['Day'], categories=days, ordered=True)

    heatmap_data = df.pivot_table(index='End Time', columns='Day', values='Duration')

    # Fill empty spots with 0s
    heatmap_data.fillna(0, inplace=True)

    # Convert index to DatetimeIndex and format x-axis ticks
    heatmap_data.index = pd.to_datetime(heatmap_data.index, format='%H:%M:%S').strftime('%H:%M')

    sns.heatmap(heatmap_data, annot=annotate, fmt=f'.{accuracy}f', linewidths=0.5)
    plt.title(title)
    plt.show()


def main():
    from projects import Projects
    import random

    projects = Projects()
    num = random.randint(1, 3)
    names = list(random.choices(projects.get_keys(), k=num))
    data = []

    for name in names:
        data += projects.get_project(name)['Session History']

    showHeatMap(data, title=f"Random Projects Heatmap ({', '.join(names)})")


if __name__ == "__main__":
    main()

