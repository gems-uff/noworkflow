def printmap(title, a_map):
    print 
    print '*' * len(title)
    print title
    print '*' * len(title)
    print
    for key in a_map:
        print key
        print a_map[key]
        print '-' * 80