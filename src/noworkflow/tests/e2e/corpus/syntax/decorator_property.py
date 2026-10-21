"""property used as a decorator, for a getter and a setter
(#281)"""


class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        self._celsius = value


reading = Temperature(20)
reading.celsius = 25
print(reading.celsius)
