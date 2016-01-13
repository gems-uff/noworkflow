import csv
import sys
import matplotlib.pyplot as plt
from simulator import simulate

def run_simulation(data_a, data_b):
    return simulate(csv_read(data_a), csv_read(data_b))

def csv_read(f):
    return list(csv.reader(open(f, 'rU'), delimiter=':'))

def extract_column(data, column):
    return [float(row[column]) for row in data]

def plot(data):
    #GetTemperature
    #GetPrecipitation
    plt.scatter(extract_column(data, 0), extract_column(data, 1), marker='o')
    plt.xlabel('Temperature')
    plt.ylabel('Precipitation')
    plt.savefig("output.png")

#Main Program
plot(run_simulation(sys.argv[1], sys.argv[2]))
