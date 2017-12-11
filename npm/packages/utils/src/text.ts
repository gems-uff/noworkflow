import {
  select as d3_select,
} from 'd3-selection';


export
function wrap(text: any, width: number) {
  text.each(function() {
    var text = d3_select(this),
        words = text.text().split(/(?=_)/).reverse(),
        word,
        line: string[] = [],
        lineNumber = 0,
        lineHeight = 1.1, // ems
        y = text.attr("y"),
        dy = parseFloat(text.attr("dy")),
        tspan = text.text(null).append("tspan").attr("x", 10).attr("y", y).attr("dy", dy + "em");
    while (word = words.pop()) {
      line.push(word);
      tspan.text(line.join(""));
      if ((tspan.node() as any).getComputedTextLength() > width) {
        line.pop();
        tspan.text(line.join(""));
        line = [word];
        tspan = text.append("tspan").attr("x", 10).attr("y", y).attr("dy", ++lineNumber * lineHeight + dy + "em").text(word);
      }
    }
  });
}