"""Properties defined with the ``@property`` decorator
(#281)

A temperature with a computed property, a setter that validates, and a
read-only property.
"""


class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius

    @property
    def fahrenheit(self):
        return self._celsius * 9 / 5 + 32

    @fahrenheit.setter
    def fahrenheit(self, value):
        self._celsius = (value - 32) * 5 / 9

    @property
    def kelvin(self):
        return self._celsius + 273.15


reading = Temperature(100)
print(reading.fahrenheit, reading.kelvin)
reading.fahrenheit = 32
print(reading._celsius)
try:
    reading.kelvin = 0
except AttributeError:
    print("kelvin is read-only")
