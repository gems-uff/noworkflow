import numpy as np
import matplotlib.pyplot as plt
from precipitation import read, prepare

def bar_graph(prec, months, years):
    prepare(prec, months, years, plt)
    plt.savefig("out.png")

months = np.arange(12) + 1
d13, d14 = read('p13.dat'), read('p14.dat')
prec = prec13, prec14 = [], []

for i in months:
    prec13.append(sum(d13[i]))
    prec14.append(sum(d14[i]))

bar_graph(prec, months, ['2013', '2014'])
