import numpy as np
import matplotlib.pyplot as plt
from precipitation import read, prepare

def bar_graph(prec, months, years):
    prepare(prec, months, years, plt)
    plt.savefig("out.png")

months = np.arange(12) + 1 
d12, d13, d14 = read('p12.dat'), read('p13.dat'), read('p14.dat')
prec = prec12, prec13, prec14 = [], [], []

for i in months:
    prec12.append(sum(d12[i]))
    prec13.append(sum(d13[i]))
    prec14.append(sum(d14[i]))

bar_graph(prec, months, ['2012', '2013', '2014'])
