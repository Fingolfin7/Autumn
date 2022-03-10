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
