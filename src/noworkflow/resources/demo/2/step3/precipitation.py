#!/usr/bin/python2

import csv
from collections import defaultdict


def read(filename):
    result = defaultdict(list)
    with open(filename, 'r') as c:
        reader = csv.reader(c, delimiter=";")
        for row in reader:
            month = int(row[1].split('/')[1])
            precipitation = float(row[3])
            result[month].append(precipitation)
    return result


def prepare(series, months, names, plt, div=.1, colors=['b', 'g', 'r']):
    fig, ax = plt.subplots()

    ax.set_ylabel('Precipitation (mm)')
    ax.set_xlabel('Month')
    ax.set_title('Precipitation by Month')
    ax.set_xticks(months + .5)
    ax.set_xticklabels(list(map(str, months)))

    half_div = div / 2.0
    width = (1.0 - div) / len(series)
    bars = []
    for i, data in enumerate(series):
        bars.append(ax.bar(months + half_div + i * width, data, width,
                           color=colors[i]))

    ax.legend(bars, names)

__VERSION__ = "1.0.1"

if __name__ == '__main__':
    import sys
    filename = sys.argv[1]
    month = sys.argv[2]
    data = read(filename)
    print(';'.join(map(str, data[int(month)])))
