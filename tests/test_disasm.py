def f(x=2):
    return x


lis = [1]
dic = {
    "x": 2
}

f(1)  # call_function
f(*lis)  # call_function_var
f(**dic)  # call_function_kw
f(*[], **dic)  # call_function_var_kw


class C(object):  # call_function

    def __enter__(self):
        x = 1
        return x

    def __exit__(self, *args, **kwargs):
        pass


def fn_dec(*args):
    def dec(fn):
        return fn
    return dec

dec1 = fn_dec("1")


@fn_dec("2")  # call_function
@dec1  # call_function
def fw(x):
    return x


@fn_dec("2")  # call_function
@dec1  # call_function
class D(object):
    pass

[a for a in lis]  # nothing
{a for a in lis}  # call_function
{a: a for a in lis}  # call_function
f(a for a in lis)  # call_function gen, call_function

with C() as r:  # WITH_CLEANUP
    pass

assert True  # nothing
assert True, "wat"  # call_function
