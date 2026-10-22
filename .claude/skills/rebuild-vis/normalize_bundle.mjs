// Splits a dev bundle into its webpack modules and regenerates each one with
// babel without comments and with the raw form of literals dropped, so that
// a diff of two bundles shows what the generated code changed and not the
// quotes, the comments or the layout. Babel's own numbering of the `this`
// captures (`_this2`) and of the regenerator contexts (`_context3`), which
// shifts whenever a closure or an async function is added or removed, is
// masked too.
//
//   node .claude/skills/rebuild-vis/normalize_bundle.mjs <bundle.js> <out dir>
//
// writes one file per module, named by its index and its webpack key, into
// <out dir>; `diff -rq` of two such directories lists the modules that
// differ, and `diff -u` of a pair is what to read. It needs the
// node_modules of src/frontend (`npm ci` there).
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const require = createRequire(join(root, "src/frontend/node_modules/"));
const parser = require("@babel/parser");
const generate = require("@babel/generator").default;

const [bundle, out] = process.argv.slice(2);
if (!bundle || !out) {
  console.error("usage: node normalize_bundle.mjs <bundle.js> <out dir>");
  process.exit(2);
}
mkdirSync(out, { recursive: true });
const text = readFileSync(bundle, "utf8");

// Each module of a dev bundle starts with `/***/ "<key>"` on a line of its
// own and its method body ends with `/***/ }`.
const header = /^\/\*\*\*\/ "([^"]+)"\n/gm;
const starts = [];
let match;
while ((match = header.exec(text))) {
  starts.push({
    key: match[1],
    at: match.index,
    bodyAt: match.index + match[0].length,
  });
}
let errors = 0;
for (let i = 0; i < starts.length; i++) {
  const end = i + 1 < starts.length ? starts[i + 1].at : text.length;
  let body = text.slice(starts[i].bodyAt, end);
  const tail = body.lastIndexOf("/***/ }");
  if (tail >= 0) {
    body = body.slice(0, tail) + "}";
  }
  body = body
    .replace(/^\/\*!.*\n(  !\*\*\*.*\n)?  \\\*+\/\n/, "")
    .replace(/^\/\*\*\*\/ /, "");
  let code;
  try {
    const ast = parser.parse("({m" + body.trim().replace(/,\s*$/, "") + "})", {
      sourceType: "script",
    });
    code = generate(ast, {
      comments: false,
      compact: false,
      jsescOption: { minimal: true },
    }).code;
  } catch (e) {
    errors++;
    code = "PARSE ERROR " + e.message + "\n" + body;
  }
  code = code
    .replace(/\b_this\d*\b/g, "_this")
    .replace(/\b_context\d*\b/g, "_context")
    .replace(/"/g, "'");
  const name =
    String(i).padStart(3, "0") +
    "-" +
    starts[i].key.replace(/[^A-Za-z0-9._@-]+/g, "_").slice(0, 120);
  writeFileSync(join(out, name + ".js"), code);
}
console.log(
  starts.length + " modules" + (errors ? ", " + errors + " not parsed" : ""),
);
