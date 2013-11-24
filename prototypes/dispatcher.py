import decorators
import fibonacci

decorators.register(fibonacci.fib)

print fibonacci.fib(100)
print decorators.cache