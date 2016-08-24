from svgwrite_title import Title
from svgwrite.shapes import Rect
from svgwrite.image import Image
from svgwrite.container import Hyperlink

WHITE = "rgb(255, 255, 255)"

class ConfigElement(object):
    def __init__(self):
        self.pos = (0, 0)
        
    def position(self, date, x):
        self.pos = (date, x)
        return self

    
class Author(ConfigElement):
    
    def __init__(self, image, name, email):
        super(Author, self).__init__()
        self.image = image
        self.name = name
        self.email = email
        
    def draw(self, builder):
        pos = builder.position(self.pos[0], builder.y + self.pos[1])
        size = (builder.image_size, builder.image_size)
        result = []
        title = self.name
        if self.email:
            title += " <{}>".format(self.email)
        color = builder.authors[self.email, "rgb(128, 128, 128)"]
        
        result.append(Rect(pos, size, fill=color, stroke=color, stroke_width=10))
        result.append(Rect(pos, size, fill=WHITE, stroke=WHITE, stroke_width=5))
        image = Image(self.image, pos, size)
        image.add(Title(title))
        result.append(image)
        return result
    
    
class Paper(ConfigElement):
    
    def __init__(self, reference, link):
        super(Paper, self).__init__()
        self.reference = reference
        self.link = link
        
    def draw(self, builder):
        pos = builder.position(self.pos[0], builder.y + self.pos[1])
        size = (builder.image_size, builder.image_size)
        image = Image("paper.png", pos, size)
        image.add(Title(self.reference))
        
        obj = Hyperlink(self.link)
        obj.add(image)
        return [obj]
    
    
class Blank(ConfigElement):
    
    def draw(self, builder):
        return []
