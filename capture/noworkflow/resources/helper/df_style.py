#!/bin/python

import argparse
import sys

def check_color(value):
    if value.upper() in ("YW", "NW"):
        return value.upper()
    if len(value.split(',')) == 3:
        return value
    raise argparse.ArgumentTypeError("%s is an invalid color/schema" % value)


def restyle(data, color="NW", direction="RL", same_line_equal=True):
    new_result = data.replace("rankdir=RL", "rankdir={}".format(direction))
    if not same_line_equal:
        new_result = new_result.replace("=\n", "= ")
    call_color = "#3A85B9"
    variable_color = "#85CBD0"
    file_color = "white"
    if color == "YW":
        call_color = "#CCFFCC"
        variable_color = "#FFFFCC"
    elif color != "NW":
        call_color, variable_color, file_color = color.split(",")
    new_result = (
        new_result
        .replace(
            "#3A85B9",
            call_color
        )
        .replace(
            "#85CBD0",
            variable_color
        )
        .replace(
            'fillcolor="white"',
            'fillcolor="{}"'.format(file_color)
        )
    )
    return new_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert lineage style")
    parser.add_argument("-c", "--color", type=check_color, default="NW",
                        help="Color schema. Possible options: NW, YW or "
                        "three color codes separated by comma, where the "
                        "first one represents calls; the second one "
                        "represents variables; and the third one "
                        "represents files. Ex: '#3A85B9,#FFFFCC,#AAAAAAA'")
    parser.add_argument("-d", "--direction", type=str, default="RL",
                        choices=["BT", "RL", "TB", "LR"],
                        help="Graphviz rankdir. Default=BT")
    parser.add_argument("-e", "--same-line-equal", action='store_true',
                        help="Show values on the same line. \n"
                        "It requires to export the values")

    args = parser.parse_args()
    userinput = "\n".join(sys.stdin.readlines())
    print(restyle(userinput, color=args.color, direction=args.direction,
          same_line_equal=args.same_line_equal))
