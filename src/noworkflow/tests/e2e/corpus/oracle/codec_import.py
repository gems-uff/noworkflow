"""Modules the script imports while it runs (#294)

A module the interpreter has not loaded yet, and ``io.open`` and
``codecs.open`` with a non-UTF-8 encoding, whose codec module Python
imports at the first use. Both imports go through noWorkflow's module
finder. Everywhere but on Windows with the standard library on another
drive than the project this runs like plain Python, and it is the theme
of non-UTF-8 encodings that file_io.py leaves out.
"""
import codecs
import io
import warnings

try:
    import colorsys
    print("colorsys:", colorsys.rgb_to_hsv(0.2, 0.4, 0.4))
except ValueError as error:
    print("import failed:", error)

# io.open and codecs.open with a non-UTF-8 encoding.
with io.open("latin.txt", "w", encoding="latin-1") as latin:
    latin.write("café crème\n")
# codecs.open is deprecated from 3.14 on; the warning is not the subject.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    latin = codecs.open("latin.txt", "r", encoding="latin-1")
    written = codecs.open("codecs.txt", "w", encoding="latin-1")
with latin:
    print("codecs:", latin.read().strip())
with written:
    written.write("ação\n")
with open("codecs.txt", "rb") as raw:
    print("codecs bytes:", raw.read())
with open("latin.txt", "rb") as raw:
    print("latin bytes:", raw.read())
