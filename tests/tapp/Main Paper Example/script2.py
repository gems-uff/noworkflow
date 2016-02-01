# script2.py
from random import random
from time import sleep


def y(i):
    sleep(.01)
    with open("y.txt", "a") as f:
        f.write("- {}\n".format(i))


def z(i):
    sleep(.1)
    with open("z.txt", "w") as f:
        f.write("- {}\n".format(i))

__version__ = "1.0.2"
