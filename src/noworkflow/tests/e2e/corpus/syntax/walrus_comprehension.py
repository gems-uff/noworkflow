"""Assignment expressions inside comprehensions, whose target binds in the
enclosing scope (PEP 572, #236)"""

data = [1, 2, 3, 4, 5]
squares = [square for x in data if (square := x * x) > 4]
print(squares, square)

total = 0
running = [total := total + x for x in data]
print(running, total)
