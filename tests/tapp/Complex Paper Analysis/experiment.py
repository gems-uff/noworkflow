import os
import json
import random


def main():
    result = {
        "x": random.randint(0, 10),
        "y": random.randint(0, 10),
    }
    result["result"] = result["x"] ** 2 + result["y"]
    print(result)
    exp_num = os.environ["EXP_NUMBER"]

    for i in range(10):
        with open("exp{}.dat".format(i), "w") as f:
            if i == int(exp_num):
                f.write(json.dumps(result))
            else:
                f.write("other files")

if __name__ == "__main__":
    main()
