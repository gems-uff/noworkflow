"""try with except, else and finally, and a finally that runs around a
return and a break"""


def divide(a, b):
    try:
        result = a / b
    except ZeroDivisionError as error:
        print("error", error)
        return None
    else:
        print("ok", result)
        return result
    finally:
        print("finally", a, b)


print(divide(4, 2), divide(1, 0))
for i in range(3):
    try:
        if i == 1:
            break
    finally:
        print("loop finally", i)
