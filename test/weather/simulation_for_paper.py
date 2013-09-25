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
  
def plot(x,y):
    kwargs = {}        
    plt.scatter(x, y, s=20, c='b', marker='o', cmap=None, norm=None, 
                    vmin=None, vmax=None, alpha=None, linewidths=None, verts=None, **kwargs)
    plt.xlabel('Temperature')
    plt.ylabel('Precipitation')
    plt.show()
    
######################################################################################    
#Main Program
dataA = csv_read('data1.dat')
dataB = csv_read('data2.dat')
#Simulation
data = run_simulation(dataA, dataB)
#GetTemperature
columnX = extract_column(data, 0)
#GetPrecipitation
columnY = extract_column(data, 1)
plot(columnX, columnY)