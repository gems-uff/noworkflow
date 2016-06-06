def filter_five_out(value):
    if value == 5:
        return -1
    return value

def filter_even_out(value):
    if value % 2 == 0:
        return -1
    return value


with open("result.txt", "w") as result:
    for i in range(10):
        value = filter_even_out(i)
        if value == -1:
            continue
        value = filter_five_out(value)
        if value != -1:
            continue
        result.write(str(value))
