import {
  json as d3_json,
} from 'd3-fetch';

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

  d3_json(url).then(function (data: any) {
    (sub as any).onclick = function() {

    }
    fn(data);
  }).catch(function(error){
    i.classList.remove("fa-spinner");
    i.classList.remove("fa-pulse");
    i.classList.add("fa-refresh");
    i.classList.add("connection-error");

    let text = document.createElement('span');
    text.classList.add("error-text")
    text.innerHTML = innertext;

    i.appendChild(text);
  });
}