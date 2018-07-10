
class SaveOutput(object):
    
    def __init__(self, name="temp", formats="svg"):
        self.name = name
        self.formats = formats
        self.lines = []
        
    def __call__(self, *text):
        self.lines.append(" ".join(map(str, text)))
        
    def _repr_svg_(self):
        return get_ipython().run_cell_magic(
            "provn", "-o {} -e {}".format(self.name, self.formats),
            self.text
        ).data
    
    def __str__(self):
        return self.text
        
    def save(self):
        with open(self.name + ".provn", "w") as f:
            f.write(self.text)
        
    @property
    def text(self):
        return "\n".join(self.lines)
