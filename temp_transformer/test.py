def test():
    pass

def test_arg(a, b, c):
    pass

def test_keyword(a=1, b=2):
    pass

def test_starargs(a, *b):
    pass

def test_kwargs(**kwargs):
    pass


test()
test_arg(1, 2, 3)
test_arg(1, b=2, c=3)
test_arg(*[4, 5, 6])
test_arg(**{'a': 7, 'b': 8, 'c': 9})
test_arg(10, *[11], **{'c': 12})

test_keyword()
test_starargs(1, 2, 3)
test_kwargs(a=1, b=2)
