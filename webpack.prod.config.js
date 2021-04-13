"use strict";

var webpack = require('webpack'),
    config = require('./webpack.common.config.js'),
    reversePath = __dirname + '/assets/js/shim/reverse.js';

config.output.filename = '[name]-[chunkhash].js';

// Allows require-ing the static file created by django-js-reverse
config.resolve.alias.reverse = reversePath;

config.devtool = false;
config.mode = 'production';
//config.devtool = 'eval-cheap-source-map';
//config.devtool = 'eval';
//config.devtool = 'inline-source-map';
//config.mode = 'development';

/*
config.watch = true;
config.watchOptions = {
    poll: 1000,
};
*/

//config.module.loaders.push({
config.module.rules.push({
    //include: reversePath,
    test: reversePath,
    //loader: 'imports-loader?this=>window!exports-loader?Urls'
    use: [//'imports-loader?this=>window!exports-loader?exports=default|Urls'
        /*{
            loader: 'imports-loader',
            options: {
                wrapper: 'window'
                //additionalCode: 'this = window;'
            }
        },
        */
        {
            loader: 'exports-loader',
            options: {
                exports: 'Urls'
            }
        }
    ]
});

/*
config.plugins.concat([
    new webpack.optimize.UglifyJsPlugin({
        mangle: {
            except: ['Urls', 'otm', 'google']
        }
    }),
    new webpack.optimize.OccurrenceOrderPlugin()
]);
*/

config.output.publicPath = '/static/';

module.exports = config;
