"""Assignment expressions (PEP 572, NamedExpr) in an if, a while and a call"""

values = [3, 8, 1, 9]
if (count := len(values)) > 3:
    print("count", count)

index = 0
while (value := values[index]) != 1:
    print("value", value)
    index += 1
print("stopped at", value, index)

print("doubled", (half := 21) * 2, half)
