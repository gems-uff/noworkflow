const path = require('path');

module.exports = {
    entry: "./src/index.ts",
    output: {
        path: path.resolve(__dirname, '..', '..', '..', 'capture', 'noworkflow', 'now', 'vis', 'static', 'dist'),
        filename: "bundle.js"
    },
    resolve: {
        // Add '.ts' and '.tsx' as a resolvable extension.
        extensions: [".webpack.js", ".web.js", ".ts", ".tsx", ".js"]
    },
    devtool: 'source-map', // if we want a source map 
    module: {
        rules: [
            {
                test: /\.ts|\.tsx$/,
                use: [{
                    loader: "awesome-typescript-loader",
                    options: {
                        useBabel: true,
                        useCache: true
                    }
                }]
            },
            {
                test: /\.css$/,
                use: [
                    'style-loader',
                    'css-loader'
                ]
            }
        ]
    }
}