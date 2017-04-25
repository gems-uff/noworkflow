import sys
import numpy as np
from precipitation import read, sum_by_month
from precipitation import write, remove_outliers
from precipitation import create_bargraph

months = np.arange(12) + 1

d13, d14 = read("p13.dat"), read("p14.dat")

for i in range(int(sys.argv[1])):
    write("temp13.dat", remove_outliers(d13), 2013)
    write("temp14.dat", remove_outliers(d14), 2014)
    d13, d14 = read("temp13.dat"), read("temp14.dat")

prec13 = sum_by_month(d13, months)
prec14 = sum_by_month(d14, months)

create_bargraph("out.png", months,
                ["2013", "2014"],
                prec13, prec14)
