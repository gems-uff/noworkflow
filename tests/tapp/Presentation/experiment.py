import numpy as np
import matplotlib.pyplot as plt
from precipitation import read, prepare

def bar_graph(years):
    global PREC, MONTHS
    prepare(PREC, MONTHS, years, plt)
    plt.savefig("out.png")

MONTHS = np.arange(12) + 1
d13, d14 = read('p13.dat'), read('p14.dat')
PREC = prec13, prec14 = [], []

for i in MONTHS:
    prec13.append(sum(d13[i]))
    prec14.append(sum(d14[i]))

bar_graph(['2013', '2014'])
