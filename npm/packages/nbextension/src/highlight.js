/**
* Register the on demand syntax highlight
*/
function register_highlight(Jupyter, events, utils, codecell) {
  var mode = 'magic_text/x-sql';
  if (!Jupyter.CodeCell.options_default.highlight_modes[mode]) {
    Jupyter.CodeCell.options_default.highlight_modes[mode] = {
      'reg':[]
    };
  }
  Jupyter.CodeCell.options_default.highlight_modes[mode].reg.push(
    /^%%now_sql/
  );
}

module.exports = {
  register_highlight: register_highlight
};