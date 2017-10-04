/**
  * Create diagonal line between two nodes
  */
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