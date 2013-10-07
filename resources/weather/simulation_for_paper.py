import csv
import time
import matplotlib.pyplot as plt

wait = 2

def run_simulation(data_a, data_b):
    global wait
    data = data_a + data_b

    time.sleep(wait)

    return data


def csv_read(f):
    reader = csv.reader(open(f, 'rU'), delimiter=':')
    data = []
    for row in reader:
        data.append(row)
    return data


def extract_column(data, column):
        col_data = []
        for row in data:
            col_data.append(float(row[column]))
        return col_data


def plot(x, y):
    kwargs = {}
    plt.scatter(x, y, s=20, c='b', marker='o', cmap=None, norm=None,
                    vmin=None, vmax=None, alpha=None, linewidths=None,
                    verts=None, **kwargs)
    plt.xlabel('Temperature')
    plt.ylabel('Precipitation')
    #plt.show()
    plt.savefig("output.png")

###############################################################################
#Main Program
data_a = csv_read('data1.dat')
data_b = csv_read('data2.dat')
#Simulation
data = run_simulation(data_a, data_b)
#GetTemperature
column_x = extract_column(data, 0)
#GetPrecipitation
column_y = extract_column(data, 1)
plot(column_x, column_y)
