import provenance
import fibonacci

provenance.register(fibonacci.fib)

print fibonacci.fib(100)
print provenance.cache