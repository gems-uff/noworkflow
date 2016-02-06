class ContextManager:

    def __enter__(self):
        return 2

    def __exit__(self, *args, **kwargs):
        pass


def func():
    context = ContextManager()

    with context as value:
        for i in range(value):
            print(i)


func()