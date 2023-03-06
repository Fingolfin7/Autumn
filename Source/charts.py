import matplotlib.pyplot as plt


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


def main():
    from projects import Projects
    from datetime import datetime
    import random

    projects = Projects()
    names = list(random.choices(projects.get_keys(), k=5))
    data = []

    for name in names:
        sess_hist = projects.get_project(name)["Session History"]

        dates = []
        durations = []

        for sess in sess_hist:
            dates.append(datetime.strptime(sess['Date'], "%m-%d-%Y"))
            durations.append(sess['Duration'] / 60)

        data.append(
            (name, (dates, durations))
        )
    for entry in data:
        print(entry)

    showScatterGraph(data)


if __name__ == "__main__":
    main()
