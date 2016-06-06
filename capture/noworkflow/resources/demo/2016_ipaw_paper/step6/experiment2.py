def filter_five_out(value):
    if value == 5:
        return -1
    return value

def filter_odd_out(value):
    if value % 2 == 1:
        return -1
    return value


with open("result.txt", "w") as result:
    for i in range(10):
        value = filter_odd_out(i)
        if value == -1:
            continue
        value = filter_five_out(value)
        if value == -1:
            continue
        result.write(str(value))
