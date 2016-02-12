import sys

def run_simulation(data_a, data_b):
    return data_a + data_b

def plot(data):
    pass

# Main Program
data_a = sys.argv[1]
data_b = sys.argv[2]
data = run_simulation(data_a, data_b)
plot(data)