import math

import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import seaborn as sns
import pandas as pd
import calplot


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
        start_time = datetime.strptime(session["Start Time"], "%H:%M:%S")
        start_bucket = start_time.replace(minute=0, second=0)
        end_time = datetime.strptime(session['End Time'], "%H:%M:%S")
        end_bucket = end_time.replace(minute=0, second=0)

        duration = float(session["Duration"]) / 60

        def split_duration_into_buckets():
            buckets = []
            running_total = 0
            for i in range(math.ceil(duration)):
                if i == 0:  # first bucket (partial)
                    partial_time = 1 - ((start_time - start_bucket).total_seconds() / 3600)
                    buckets.append([start_bucket, partial_time])
                    running_total += partial_time
                else:
                    buckets.append([start_bucket + timedelta(hours=i), 1])
                    running_total += 1

            partial_time = (end_time - end_bucket).total_seconds() / 3600

            # check if this fraction plus the sum of all bucket fractions in buckets exceeds duration
            if partial_time + running_total > duration:
                # if it does, remove the last bucket from buckets
                buckets = buckets[:-1]

            if partial_time != 0:
                buckets.append([end_bucket, partial_time])

            # # filter out any buckets with zero duration using a lambda function
            # buckets = list(filter(lambda x: x[1] != 0, buckets))

            # return the list of buckets
            return buckets

        split_buckets = split_duration_into_buckets()

        # append each bucket with the day to the data list
        for bucket in split_buckets:
            data.append([day] + bucket)

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

    print(heatmap_data)

    # Convert index to DatetimeIndex and format x-axis ticks
    heatmap_data.index = pd.to_datetime(heatmap_data.index, format='%H:%M:%S').strftime('%H:%M')

    sns.heatmap(heatmap_data, annot=annotate, fmt=f'.{accuracy}f')
    plt.title(title)
    plt.show()


# function to show calendar heatmap
def showCalendar(project_histories: list, title: str = "Projects Calender", annotate=False):
    # Initialize variables
    current_date = None
    day_total = 0.0
    data = []
    dates = []

    for session in project_histories:
        if current_date != session['Date']:
            # Print output for previous date
            if current_date is not None:
                data.append(day_total / 60)  # convert to hours
                dates.append(current_date)

            # Reset variables for new date
            current_date = session['Date']
            day_total = 0.0

        # add duration to day total
        day_total += session['Duration']

    # Print output for last date
    if current_date is not None:
        data.append(day_total / 60)
        dates.append(current_date)

    # use pandas to convert the dates into a datetime format
    dates = pd.to_datetime(dates, format="%m-%d-%Y")

    # Convert data to DataFrame
    df = pd.DataFrame(index=dates, data=data, columns=['Duration'])

    # make pandas series from the dataframe
    calendar_series = pd.Series(df['Duration'].values, index=df.index)

    if annotate:
        calplot.calplot(calendar_series, cmap='YlGn', textformat='{:.1f}', linewidth=0.5,
                        yearlabel_kws={'fontname': 'sans-serif'})
    else:
        calplot.calplot(calendar_series, cmap='YlGn', linewidth=0.5,
                        yearlabel_kws={'fontname': 'sans-serif'})

    plt.title(title)
    plt.show()


def main():
    from projects import Projects
    import random

    projects = Projects()
    num = random.randint(1, 3)
    # names = list(random.choices(projects.get_keys(), k=num))
    names=['Adaski']
    data = []

    for name in names:
        data += projects.get_project(name)['Session History']
    showHeatMap(data, title=f"Random Projects Heatmap ({', '.join(names)})")


if __name__ == "__main__":
    main()
