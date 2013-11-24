import collections

def print_list(a_list):
    for item in a_list:
        print '\t' + item

def print_map(title, a_map):
    print 
    print '*' * len(title)
    print title
    print '*' * len(title)
    print
    for key in a_map:
        print key
        try:
            print_list(a_map[key])
        except Exception:
            print a_map[key]
        print '-' * 80

def print_nested(key, a_map_of_lists, processed = set(), level = 0):
    print '\t' * level, key
    if not key in processed:
        processed.add(key)
        for value in a_map_of_lists[key]:
            print_nested(value, a_map_of_lists, processed, level + 1)
    else:
        print '\t' * (level + 1), '...'
        
def print_flat(key, a_map_of_lists, processed = set(), level = 0):
    if not key in processed:
        print '\t' * level, key
        processed.add(key)
        for value in a_map_of_lists[key]:
            print_flat(value, a_map_of_lists, processed, 1)
            
def pp_map(a_map, processed, level):
    for key in a_map:
        print "\t" * level, key
        pp(a_map[key], processed, level + 1)
    
def pp_sequence(a_sequence, processed, level):
    for item in a_sequence:
        pp(item, processed, level + 1)
    
def pp(an_object, processed = set(), level = 0):
    if id(an_object) in processed:
        print '\t' * level, '<RECURSION>'
    else:
        processed.add(id(an_object))
        if isinstance(an_object, collections.Mapping):
            pp_map(an_object, processed, level)
        elif isinstance(an_object, list) or isinstance(an_object, set):
            pp_sequence(an_object, processed, level)
        else:
            print '\t' * level, an_object