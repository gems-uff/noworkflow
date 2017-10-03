import {
  select as d3_select,
} from 'd3-selection';

import {
  json as d3_json,
} from 'd3-request';


export
function diagonal(s: any, d: any): string {
  if (s.dy == undefined) {
    s.dy = 0;
  }
  if (d.dy == undefined) {
    d.dy = 0;
  }
  let path = `M ${s.x} ${(s.y + s.dy)}
          C ${(s.x + d.x) / 2} ${(s.y + s.dy)},
            ${(s.x + d.x) / 2} ${(d.y + d.dy)},
            ${d.x} ${(d.y + d.dy)}`

  return path;
}


export
function json(innertext:string, sub: Element, url: string, fn: (data: any) => void) {
  let i = document.createElement('i');
  i.classList.add("loading");
  i.classList.add("fa");
  i.classList.add("fa-spinner");
  i.classList.add("fa-pulse");

  sub.innerHTML = "";
  sub.appendChild(i);
  (sub as any).onclick = function() {
    json(innertext, sub, url, fn);
  }

  d3_json(url, (error: any, data: any) => {
    if (error) {
      i.classList.remove("fa-spinner");
      i.classList.remove("fa-pulse");
      i.classList.add("fa-refresh");
      i.classList.add("connection-error");

      let text = document.createElement('span');
      text.classList.add("error-text")
      text.innerHTML = innertext;

      i.appendChild(text);
    } else {
      (sub as any).onclick = function() {

      }
      fn(data);
    }

  });
}


export
function makeid(): any {
  var text = "";
  var possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

  for (var i = 0; i < 5; i++)
    text += possible.charAt(Math.floor(Math.random() * possible.length));

  return text;
}


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
