const path = require('path');
var version = require('./package.json').version;


var loaders = [
  {
    test: /\.js$/,
    include: [path.join(__dirname, 'src')],
    loader: 'babel-loader',
    query: { presets: ['env'] }
  },
  { test: /\.json$/, loader: 'json-loader' },
  { test: /\.css$/, loader: 'style-loader!css-loader' },
  { test: /\.html$/, loader: 'file-loader' },
  { test: /\.(jpg|png|gif)$/, loader: 'file-loader' },
  {
    test: /\.woff2(\?v=\d+\.\d+\.\d+)?$/,
    loader: 'url-loader?limit=10000&mimetype=application/font-woff'
  },
  {
    test: /\.woff(\?v=\d+\.\d+\.\d+)?$/,
    loader: 'url-loader?limit=10000&mimetype=application/font-woff'
  },
  {
    test: /\.ttf(\?v=\d+\.\d+\.\d+)?$/,
    loader: 'url-loader?limit=10000&mimetype=application/octet-stream'
  },
  { test: /\.eot(\?v=\d+\.\d+\.\d+)?$/, loader: 'file-loader' },
  {
    test: /\.svg(\?v=\d+\.\d+\.\d+)?$/,
    loader: 'url-loader?limit=10000&mimetype=image/svg+xml'
  }
];


var base = {
  output: {
    libraryTarget: 'amd',
    devtoolModuleFilenameTemplate: 'webpack:///[absolute-resource-path]'
  },
  devtool: 'source-map',
  module: { loaders },
  externals: ['$']
};


module.exports = [
  /**
   * Notebook extension
   * 
   * This bundle only contains the part of the JavaScript that is run on
   * load of the notebook. This section generally only performs
   * some configuration for requirejs, and provides the legacy
   * "load_ipython_extension" function which is required for any notebook
   * extension.
   */
  Object.assign({}, base, {
    entry: path.join(__dirname, 'src', 'extension.js'),
    output: Object.assign({}, base.output, {
      filename: 'extension.js',
      path: path.join(
        __dirname,
        '..',
        '..',
        '..',
        'capture',
        'noworkflow',
        'jupyter'
      )
    }),
    externals: [
      'nbextensions/noworkflow/index',
      'base/js/namespace',
      'base/js/events',
      'base/js/utils',
      'notebook/js/codecell',
      '$'
    ]
  }),
  /**
   * Bundle for the notebook containing the custom widget views and models
   * 
   * This bundle contains the implementation for the custom widget views and
   * custom widget.
   * 
   * It must be an amd module
   */
  Object.assign({}, base, {
    entry: path.join(__dirname, 'src', 'index.js'),
    output: Object.assign({}, base.output, {
      filename: 'index.js',
      path: path.join(
        __dirname,
        '..',
        '..',
        '..',
        'capture',
        'noworkflow',
        'jupyter'
      )
    })
  }),
  /**
   * Embeddable noworkflow_nb bundle
   * 
   * This bundle is generally almost identical to the notebook bundle
   * containing the custom widget views and models.
   * 
   * The only difference is in the configuration of the webpack public path
   * for the static assets.
   * 
   * It will be automatically distributed by unpkg to work with the static
   * widget embedder.
   * 
   * The target bundle is always `lib/index.js`, which is the path required
   * by the custom widget embedder.
   */
  Object.assign({}, base, {
    entry: './src/embed.js',
    output: Object.assign({}, base.output, {
      filename: 'index.js',
      path: path.join(__dirname, 'embed'),
      publicPath: 'https://unpkg.com/noworkflow@' +
        version +
        '/lib/'
    })
  })
];
