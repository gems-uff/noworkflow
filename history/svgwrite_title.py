from svgwrite.base import BaseElement

class Title(BaseElement):
    elementname = 'title'
    def __init__(self, title, *args, **kwargs):
        super(Title, self).__init__(*args, **kwargs)
        self.set_desc(title=title)