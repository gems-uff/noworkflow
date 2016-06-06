#!/usr/bin/python2

import csv
import numpy as np
import matplotlib.pyplot as plt

from itertools import chain
from collections import defaultdict


def read(filename):
    result = defaultdict(list)
    with open(filename, "r") as c:
        reader = csv.reader(c, delimiter=";")
        for row in reader:
            month = int(row[1].split("/")[1])
            precipitation = float(row[3])
            result[month].append(precipitation)
    return result

def write(filename, data, year):
    with open(filename, "w") as c:
        writer = csv.writer(c, delimiter=";")
        for month in sorted(data.keys()):
            for day, value in enumerate(data[month]):
                writer.writerow([
                    83743, "{:02}/{:02}/{}".format(day + 1, month, year),
                    1200, value])

def remove_outliers(data, thresh=2.5):
    full_data = np.asarray(tuple(chain.from_iterable(data[i]
                                 for i in sorted(data.keys()))))
    non_zeros = full_data != 0
    median = np.median(full_data[non_zeros])

    result = {}
    for month in data:
        values = np.asarray(data[month])[:, None]
        diff = np.sum((values - median)**2, axis=-1)
        diff = np.sqrt(diff)
        med_abs_deviation = np.median(diff)

        modified_z_score = 0.6745 * diff / med_abs_deviation

        outliers = modified_z_score > thresh
        non_outliers = modified_z_score < thresh

        new_data = np.zeros(len(values))
        new_data[non_outliers] = values[non_outliers]
        new_data[outliers] = median

        result[month] = new_data.tolist()
    return result


def prepare(series, months, names, div=.1, colors=["b", "g", "r"]):
    fig, ax = plt.subplots()

    ax.set_ylabel("Precipitation (mm)")
    ax.set_xlabel("Month")
    ax.set_title("Precipitation by Month")
    ax.set_xticks(months + .5)
    ax.set_xticklabels(list(map(str, months)))

    half_div = div / 2.0
    width = (1.0 - div) / len(series)
    bars = []
    for i, data in enumerate(series):
        bars.append(ax.bar(months + half_div + i * width, data, width,
                           color=colors[i]))

    ax.legend(bars, names)

def create_bargraph(output, months, years, *prec):
    prepare(prec, months, years)
    plt.savefig(output)

def sum_by_month(data, months):
    return [sum(data[i]) for i in months]

__VERSION__ = "1.1.0"

if __name__ == "__main__":
    import sys
    filename = sys.argv[1]
    month = sys.argv[2]
    data = read(filename)
    print(";".join(map(str, data[int(month)])))
