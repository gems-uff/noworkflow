import './index.css';

/**
 * Register the mime type and append_mime function with the notebook's
 * output area
 */
export function register_renderer(notebook, trial, history, utils, d3_selection) {
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
      height: data.height
    });
    graph.load(data, data.trial1, data.trial2);
    return div;
  };


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
}

/**
 * Re-render cells with output data of 'application/unittest.status+json' mime type
 */
export function render_cells(notebook) {
  /* Get all cells in notebook */
  notebook.get_cells().forEach(cell => {
    if (cell.output_area) {
      if (
        cell.output_area.outputs.find(out => out.data && (
          out.data['application/noworkflow.history+json'] ||
          out.data['application/noworkflow.trial+json']
        ))
      ) {
        notebook.render_cell_output(cell);
      }
    }
  });
}
