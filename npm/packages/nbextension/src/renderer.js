require('./index.css');

/**
 * Register the mime type and append_mime function with the notebook's
 * output area
 */
function register_renderer(notebook, trial, history, utils, d3_selection) {
  /* Get an instance of output_area from a CodeCell instance */
  const { output_area } = notebook
    .get_cells()
    .reduce((result, cell) => cell.output_area ? cell : result, {});

  /* History mime */
  const append_history = function(data, metadata, element) {
    var div = document.createElement('div');
    element.append(div);
    var graph = new history.HistoryGraph('history-' + utils.makeid(), div, {
      width: data.width,
      height: data.height,
      hintMessage: "",
    });
    graph.load(data);
    return div;
  };

  /* Trial mime */
  const append_trial = function(data, metadata, element) {
    var div = document.createElement('div');
    element.append(div);
    var graph = new trial.TrialGraph('trial-' + utils.makeid(), div, {
      width: data.width,
      height: data.height,
      genDataflow: false
    });
    graph.load(data, data.trial1, data.trial2);
    return div;
  };

  /* Code mime */
  const append_code = function(data, metadata, element) {
    var code_id = utils.makeid();
    var div = document.createElement('div');
    var textarea = document.createElement('textarea');
    div.appendChild(textarea);
    textarea.id = code_id;
    textarea.value = data.code;
    var code_mirror = CodeMirror.fromTextArea(
      textarea, {
        lineNumbers: true,
        styleSelectedText: true,
        mode: "python",
        readOnly: true
    });
    element.append(div)
    code_mirror.setValue(data.code);
    var marks = data.marks;
    marks.forEach(function(mark) {
      code_mirror.markText.apply(code_mirror, mark)
    });

    if (data.showSelection) {
      $(code_mirror.getWrapperElement()).after(
        "<input type='text' id='"+code_id+"-selection'></input>"
      );
      code_mirror.on('cursorActivity', function(cm) {
        var tcursor = cm.getCursor(true);
        var fcursor = cm.getCursor(false);
        $("#"+code_id+"-selection").val(
          "[" + tcursor.line + ", " + tcursor.ch + "], "+
          "[" + fcursor.line + ", " + fcursor.ch + "]"
        );
      });
    }
    
    setTimeout(function() {
      code_mirror.refresh();
    },1);
    return div;
  }


  /**
   * Register the mime type and append_history function with output_area
   */
  output_area.register_mime_type(
    'application/noworkflow.history+json', append_history, {
      safe: true,
      index: 0
    }
  );

  output_area.register_mime_type(
    'application/noworkflow.trial+json', append_trial, {
      safe: true,
      index: 0
    }
  );

  output_area.register_mime_type(
    'application/noworkflow.code+json', append_code, {
      safe: true,
      index: 0
    }
  );
}

/**
 * Re-render cells with output data of 'application/unittest.status+json' mime type
 */
function render_cells(notebook) {
  /* Get all cells in notebook */
  notebook.get_cells().forEach(cell => {
    if (cell.output_area) {
      if (
        cell.output_area.outputs.find(out => out.data && (
          out.data['application/noworkflow.history+json'] ||
          out.data['application/noworkflow.trial+json'] ||
          out.data['application/noworkflow.code+json']
        ))
      ) {
        notebook.render_cell_output(cell);
      }
    }
  });
}


module.exports = {
  register_renderer: register_renderer,
  render_cells: render_cells
};