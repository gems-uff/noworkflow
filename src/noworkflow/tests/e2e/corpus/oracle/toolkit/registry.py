"""Module state shared by every importer"""
KINDS = {}
LOADS = []


def register(name, factory):
    KINDS[name] = factory
    LOADS.append(name)


def build(name, *args):
    return KINDS[name](*args)
