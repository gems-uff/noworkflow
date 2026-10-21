const path = require('path');

module.exports = {
    mode: 'development',
    entry: "./src/index.ts",
    output: {
        path: path.resolve(__dirname, '..', '..', '..', 'noworkflow', 'now', 'vis', 'static', 'dist'),
        filename: "bundle.js"
    },
    resolve: {
        // Add '.ts' and '.tsx' as a resolvable extension.
        extensions: [".webpack.js", ".web.js", ".ts", ".tsx", ".js"],
        alias: {
            // The CommonJS build of @viz-js/viz: its ES module build reads
            // import.meta.url, which webpack replaces with the file:// URL of
            // the module on the machine that builds, so the committed bundle
            // would carry the path of the checkout.
            "@viz-js/viz$": require.resolve("@viz-js/viz"),
        },
        fallback: {
            crypto: false,
            stream: require.resolve("stream-browserify"),
            buffer: require.resolve("buffer/"),
            vm: require.resolve("vm-browserify"),
            fs: false,
            child_process: false,
            // Required by that CommonJS build only where there is no document.
            url: false
        }
    },
    devtool: 'source-map', // if we want a source map 
    module: {
        rules: [
            {
                test: /\.ts|\.tsx$/,
                loader: "babel-loader"
            },
            {
                test: /\.css$/,
                use: [
                    'style-loader',
                    'css-loader'
                ]
            },
            {
                test: /\.(png|jpe?g|gif)$/i,
                use: [
                  {
                    loader: 'file-loader',
                  },
                ],
            },
        ]
    }
}