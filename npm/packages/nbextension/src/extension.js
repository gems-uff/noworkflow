/**
 * This file contains the javascript that is run when the notebook is loaded.
 * It contains some requirejs configuration and the `load_ipython_extension` 
 * which is required for any notebook extension.
 */

/**
 * Configure requirejs.
 */
if (window.require) {
  window.require.config({
    map: {
      '*': {
        'noworkflow': 'nbextensions/noworkflow/index'
      }
    }
  });
}



/**
 * Export the required load_ipython_extention.
 */
export function load_ipython_extension() {
  define([
    'nbextensions/noworkflow/index',
    'base/js/namespace',
    'base/js/events',
    'base/js/utils',
    'notebook/js/codecell',
    'd3-selection',
    '@noworkflow/trial',
    '@noworkflow/history',
    '@noworkflow/utils',

  ], (
    Extension,
    Jupyter,
    events,
    utils,
    codecell,
    d3_selection,
    trial,
    history,
    nowutils
  ) => {
    console.log("<<<LOAD noworkflow 2>>>");
    let notebook = Jupyter.notebook;
    Extension.register_renderer(
      notebook, trial, history, nowutils, d3_selection
    );
    Extension.render_cells(notebook);
  });
}
