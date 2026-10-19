"""Imported on demand with importlib.import_module"""
FACTORS = {"m": 1.0, "cm": 0.01, "km": 1000.0}
IMPORTS = []
IMPORTS.append(__name__)


def convert(value, source, target):
    return value * FACTORS[source] / FACTORS[target]
