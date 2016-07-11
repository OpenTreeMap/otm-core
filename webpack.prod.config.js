"use strict";

var webpack = require('webpack'),
    config = require('./webpack.common.config.js'),
    reversePath = __dirname + '/assets/js/shim/reverse.js';

config.output.filename = '[name]-[chunkhash].js';

// Allows require-ing the static file created by django-js-reverse
config.resolve.alias.reverse = reversePath;

config.devtool = 'source-map';

config.module.loaders.push({
    include: reversePath,
    loader: 'imports?this=>window!exports?Urls'
});

config.plugins.concat([
    new webpack.optimize.UglifyJsPlugin({
        mangle: {
            except: ['Urls', 'otm', 'google']
        }
    }),
    new webpack.optimize.OccurrenceOrderPlugin()
]);

config.output.publicPath = '/static/';

module.exports = config;
