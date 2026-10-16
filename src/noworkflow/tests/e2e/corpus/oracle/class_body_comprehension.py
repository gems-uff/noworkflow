"""Comprehensions in a class body (#NEW:class-body-comprehension)

Lookup tables computed when the class is created: a list and a dict
comprehension at class level, whose iterables use class attributes.
"""


class Weekdays:
    NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday")
    SHORT = [name[:3] for name in NAMES]
    INDEX = {name: number for number, name in enumerate(NAMES, start=1)}


print(Weekdays.SHORT, Weekdays.INDEX["friday"])
