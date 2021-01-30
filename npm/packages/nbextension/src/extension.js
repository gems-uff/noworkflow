// This file contains the javascript that is run when the notebook is loaded.
// It contains some requirejs configuration and the `load_ipython_extension`
// which is required for any notebook extension.
//
// Some static assets may be required by the custom widget javascript. The base
// url for the notebook is not known at build time and is therefore computed
// dynamically.
'use strict';
__webpack_public_path__ = document.querySelector('body').getAttribute('data-base-url') + 'nbextensions/noworkflow/';


// Configure requirejs
window['requirejs'].config({
  map: {
    '*': {
      'noworkflow': 'nbextensions/noworkflow/index',
      'd3-selection': 'nbextensions/noworkflow/extension',
      '@noworkflow/trial': 'nbextensions/noworkflow/extension',
      '@noworkflow/history': 'nbextensions/noworkflow/extension',
      '@noworkflow/utils': 'nbextensions/noworkflow/extension',
    }
  }
});

// Export the required load_ipython_extension
function load_ipython_extension() {
  return new Promise(function(resolve) {
    requirejs([
      'nbextensions/noworkflow/index',
      'base/js/namespace',
      'base/js/events',
      'base/js/utils',
      'notebook/js/codecell',
      'd3-selection',
      '@noworkflow/trial',
      '@noworkflow/history',
      '@noworkflow/utils',
    ], function(
      Extension,
      Jupyter,
      events,
      utils,
      codecell,
      d3_selection,
      trial,
      history,
      nowutils
    ) {
      require('./index.css');
      console.log("<<<LOAD noworkflow 2>>>");
      let notebook = Jupyter.notebook;
      Extension.register_renderer(
        notebook, trial, history, nowutils, d3_selection
      );
      Extension.render_cells(notebook);
      Extension.register_highlight(Jupyter, events, utils, codecell)
      resolve();
    })
  });
} 

module.exports = {
  load_ipython_extension: load_ipython_extension,
  ...require('d3-selection'),
  ...require('@noworkflow/trial'),
  ...require('@noworkflow/history'),
  ...require('@noworkflow/utils')
}
