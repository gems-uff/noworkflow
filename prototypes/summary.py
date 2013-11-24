import re
import string


def repetitions(s):
    r = re.compile(r"(.*)\1+")
    i = 0
    for match in r.finditer(s):
        pos = string.find(s, match.group(1), i)
        if pos > i:
            yield (s[i], 1)
            i = i + 1
        if len(match.group(1)) > 0:
            yield (match.group(1), len(match.group(0)) / len(match.group(1)))
            i = i + (len(match.group(1) * (len(match.group(0)) / len(match.group(1)))))
    #deals with the end of the string
    if (i < len(s)):
        for i in range(i, len(s)):
            yield (s[i], 1)

print "blablabla"
print list(repetitions("blablabla"))

print "rablabla"
print list(repetitions("rablabla"))

print "aaaaa"
print list(repetitions("aaaaa"))

print "aaaaablablabla"
print list(repetitions("aaaaablablabla"))

print "xxadxxad"
print list(repetitions('xxadxxad'))

s = 'function1function2function1function2function3function1function1function1'
print s
print list(repetitions(s))