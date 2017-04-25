DRY_RUN = True

from external import process







def show(number):
    if number not in (1, 7):
        return "unhappy number"
    return "happy number"

n = 10
final = process(n)
if DRY_RUN:
    final = 1
print(show(final))
