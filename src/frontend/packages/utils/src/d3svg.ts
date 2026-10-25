/**
 * Create diagonal line between two nodes
 */
export function diagonal(s: any, d: any): string {
  if (s.dy == null) {
    s.dy = 0;
  }
  if (d.dy == null) {
    d.dy = 0;
  }
  const path = `M ${s.x} ${s.y + s.dy}
          C ${(s.x + d.x) / 2} ${s.y + s.dy},
            ${(s.x + d.x) / 2} ${d.y + d.dy},
            ${d.x} ${d.y + d.dy}`;

  return path;
}
