def check(value):
    raise ValueError("bad value {}".format(value))


print("before")
check(3)
