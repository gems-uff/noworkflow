"""match (PEP 634): literal, or, as, value, sequence, mapping, class, guard
and wildcard patterns (collecting them is #156, not checked here)"""


class Point:
    __match_args__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y


class Color:
    BLUE = "blue"


def describe(subject):
    match subject:
        case 0:
            return "literal zero"
        case "red" | "green" as color:
            return "or-pattern bound to " + color
        case Color.BLUE:
            return "value pattern blue"
        case [first, *rest]:
            return "sequence first={} rest={}".format(first, rest)
        case {"kind": "circle", "radius": radius}:
            return "mapping radius={}".format(radius)
        case Point(x=0, y=y):
            return "class on the y axis y={}".format(y)
        case Point(x, y) if x == y:
            return "guard on the diagonal {}".format(x)
        case Point():
            return "class elsewhere"
        case int(number) if number > 100:
            return "guard big {}".format(number)
        case _:
            return "wildcard {!r}".format(subject)


SUBJECTS = [
    0, "red", "blue", [1, 2, 3], {"kind": "circle", "radius": 2},
    Point(0, 5), Point(3, 3), Point(1, 2), 150, 7, None,
]
for subject in SUBJECTS:
    print(describe(subject))
