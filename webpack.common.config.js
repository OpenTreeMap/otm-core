"use strict";

var Webpack = require('webpack'),
    glob = require('glob'),
    path = require('path'),
    _ = require('lodash'),
    BundleTracker = require('webpack-bundle-tracker'),
    ExtractTextPlugin = require("extract-text-webpack-plugin"),
    autoprefixer = require('autoprefixer');

function d(path) {
    // Turns a relative path from 'opentreemap/' into an absolute path
    return __dirname +'/' + path;
}

function getEntries() {
    return {
        'demo': './opentreemap/modeling/js/src/modeling.js'
    };
}

function getAliases() {
    var aliases = {
            'modeling': d('opentreemap/modeling/js/src/')
        };
    return _.merge(aliases, shimmed);
}

var shimmed = {
    typeahead: d('assets/js/shim/typeahead.jquery.js'),
    bootstrap: d('assets/js/shim/bootstrap.js'),
    'bootstrap-slider': d('assets/js/shim/bootstrap-slider.js')
};

module.exports = {
    entry: getEntries(),
    output: {
        filename: '[name].js',
        path: d('static'),
        sourceMapFilename: '[file].map'
    },
    module: {
        loaders: [{
            include: [shimmed["bootstrap-slider"]],
            loader: "imports?bootstrap"
        }, {
            test: /\.scss$/,
            loader: ExtractTextPlugin.extract(['css', 'postcss-loader', 'sass'], {extract: true})
        }, {
            test: /\.woff($|\?)|\.woff2($|\?)|\.ttf($|\?)|\.eot($|\?)|\.svg($|\?)/,
            loader: 'url',
        }, {
            test: /\.(jpg|png|gif)$/,
            loader: 'url?limit=25000',
        }]
    },
    resolve: {
        alias: getAliases(),
        // Look in node_modules, our shared asset 'js/vendor/' and each Django
        // app's 'js/vendor/' for modules that support a module system
        root: [d("assets/js/vendor"), d("node_modules")].concat(glob.sync(d('opentreemap/*/js/vendor/')))
    },
    resolveLoader: {
        root: d("node_modules")
    },
    plugins: [
        // Provide jquery and Leaflet as global variables, which gets rid of
        // most of our shimming needs
        // NOTE: the test configuration relies on this being the first plugin
        new Webpack.ProvidePlugin({
            jQuery: "jquery",
            "window.jQuery": "jquery",
            L: "leaflet"
        }),
        new ExtractTextPlugin('css/main.css', {allChunks: true}),
        new BundleTracker({path: d('static'), filename: 'webpack-stats.json'})
    ],
    postcss: function () {
        return [autoprefixer];
    }
};
