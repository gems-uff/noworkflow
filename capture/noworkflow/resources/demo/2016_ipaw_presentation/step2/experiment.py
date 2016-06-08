import numpy as np
from precipitation import read, sum_by_month
from precipitation import create_bargraph

months = np.arange(12) + 1

d12, d13, d14 = read("p12.dat"), read("p13.dat"), read("p14.dat")

prec12 = sum_by_month(d12, months)
prec13 = sum_by_month(d13, months)
prec14 = sum_by_month(d14, months)

create_bargraph("out.png", months,
	            ["2012", "2013", "2014"],
	            prec12, prec13, prec14)
