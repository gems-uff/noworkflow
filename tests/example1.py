"""First example"""
import example2
import re


def a(var1):
    def x():
        pass
    if var1 > 0:
        b()
        c()


def b():
    """function b calls c"""
    c()


def c():
    a(0)


x = 10
y = a(x)
x = 5
c()
example2.e(x)
print(40)
b()
