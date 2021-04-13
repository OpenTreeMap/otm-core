"use strict";

var webpack = require('webpack'),
    config = require('./webpack.common.config.js'),
    reversePath = __dirname + '/assets/js/shim/reverse.js';

    host = process.env.WEBPACK_DEV_SERVER || 'http://localhost:6062/';

// Add webpack-dev-server to the common entry bundle
config.entry['js/treemap/base'] = [
    'webpack-dev-server/client?' + host,
    'webpack/hot/dev-server',
    './opentreemap/treemap/js/src/base.js'
];

//config.output.publicPath = host + 'static/';
config.output.publicPath = '/static/';
//config.output.pathInfo = true;
config.output.pathinfo = true;

config.module.rules.push({
    include: reversePath,
    //loader: 'imports?this=>window!exports?Urls'
    use: ['imports?this=>window!exports?Urls']
});

//config.debug = true;

config.devtool = 'eval';

config.plugins = config.plugins.concat([
    new webpack.HotModuleReplacementPlugin()
]);

// Allows require-ing the global variable created by django-js-reverse
config.externals = {
    reverse: "Urls"
};

config.watchOptions = {
    poll: 1000,
};

// Proxy all requests for static assets to nginx
config.devServer = {
    proxy: {
        '/static/*': {
            target: 'http://localhost',
            secure: false
        }
    }
};

module.exports = config;
