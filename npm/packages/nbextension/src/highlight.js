/**
* Register the on demand syntax highlight
*/
export function register_highlight(Jupyter, events, utils, codecell) {
  function activateMonitor(cell) {
    if ((cell instanceof codecell.CodeCell)) {
      /* Define event for checking the highlight */
      function changecode() {
        let split = cell.code_mirror.getValue().split(" ");
        if (split && split[0] == "%%write" && split.length > 2) {
          utils.requireCodeMirrorMode(split[1], (mode) => {
            console.log('Found:', mode, split[1]);
            var mode = 'magic_' + split[1];
            if (!Jupyter.CodeCell.options_default.highlight_modes[mode]) {
                Jupyter.CodeCell.options_default.highlight_modes[mode] = {
                    'reg':[]
                };
            }
            var regex = new RegExp('^%%write ' + split[1]);
            if (Jupyter.CodeCell.options_default.highlight_modes[mode].reg.indexOf(regex) == -1) {
              Jupyter.CodeCell.options_default.highlight_modes[mode].reg.push(
                  regex
              );
            }
            cell.auto_highlight();
          }, () => console.log('Not found:', split[1]));
        }
      }
      /* Set event on code change */
      var pending;
      cell.code_mirror.on('change', function() {
        clearTimeout(pending);
        pending = setTimeout(changecode, 400);
      });
      changecode();
    }
  }


  function initExistingCells() {
    var cells = Jupyter.notebook.get_cells();
    var ncells = Jupyter.notebook.ncells();
    for (var i = 0; i < ncells; i++) {
      var cell = cells[i];
      activateMonitor(cells[i]);
    }
    events.on('create.Cell', (event, nbcell) => activateMonitor(nbcell.cell));
  }


  if (Jupyter.notebook._fully_loaded) {
    setTimeout(function () {
      console.log('Dojotools: Wait for', 1000, 'ms');
      initExistingCells();
    }, 1000);
  } else {
    events.one('notebook_loaded.Notebook', initExistingCells);
  }
}