"""while with else, break and continue"""

n = 0
while n < 5:
    n += 1
    if n == 2:
        continue
    if n == 4:
        break
    print("n", n)
else:
    print("no break")

m = 0
while m < 2:
    m += 1
else:
    print("else after", m)
