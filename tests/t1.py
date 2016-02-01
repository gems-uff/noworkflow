def a():
    def b():
        print "b"
    print "a"

print a.b()
