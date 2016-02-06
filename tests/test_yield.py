def new_range(maximum):
    j = 0
    while j < maximum:
        yield j
        j += 1

for k in new_range(3):
    print(k)
print(k)
