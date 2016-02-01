# script1.py
from script2 import y, z


def x(i):
    if i % 2:
        z(i)
        return y(i)
    return z(i)

if __name__ == "__main__":
    for i in range(3):
        x(i)
    z(i)
