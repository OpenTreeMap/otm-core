"use strict";

var webpack = require('webpack'),
    config = require('./webpack.common.config.js'),

    host = process.env.WEBPACK_DEV_SERVER || 'http://localhost:6062/';

// Add webpack-dev-server to the common entry bundle
config.entry['demo'] = [
    config.entry['demo'],
    'webpack-dev-server/client?' + host,
    'webpack/hot/dev-server'];

config.output.publicPath = host + 'static/';
config.output.pathInfo = true;

config.debug = true;

config.devtool = 'eval';

config.plugins = config.plugins.concat([
    new webpack.HotModuleReplacementPlugin()
]);

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
