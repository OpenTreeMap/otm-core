"use strict";

var Webpack = require('webpack'),
    glob = require('glob'),
    path = require('path'),
    _ = require('lodash'),
    BundleTracker = require('webpack-bundle-tracker'),
    MiniCssExtractPlugin = require('mini-css-extract-plugin'),
    autoprefixer = require('autoprefixer');

function d(path) {
    // Turns a relative path from 'opentreemap/' into an absolute path
    return __dirname +'/' + path;
}

function getEntries() {
    var files = glob.sync('./opentreemap/*/js/src/*.js'),
        entries = {};

    //var files = [
    //    ...glob.sync('./opentreemap/treemap/js/src/*.js'),
    //    ...glob.sync('./opentreemap/frontend/js/src/*.js'),
    //    ],
    //    entries = {};
    files.forEach(function(file) {
        var app = file.split(path.sep)[2],
            basename = path.basename(file, '.js');
        entries['js/' + app + '/' + basename] = file;
    });
    return entries;
}

function getAliases() {
    var dirs = glob.sync('opentreemap/*/js/src/*/'),
        aliases = {};
    dirs.forEach(function(thePath) {
        var parts = thePath.split(path.sep),
            app = parts[1],
            dir = parts[4],
            alias = app + path.sep + dir,
            target = thePath.slice(0, -1);
        aliases[alias] = d(target);
    });
    return _.merge(aliases, shimmed);
}

var shimmed = {
    leafletbing: d('assets/js/shim/leaflet.bing.js'),
    utfgrid: d('assets/js/shim/leaflet.utfgrid.js'),
    typeahead: d('assets/js/shim/typeahead.jquery.js'),
    //bootstrap: d('assets/js/shim/bootstrap.js'),
    jqueryFileUpload: d('assets/js/shim/jquery.fileupload.js'),
    jqueryIframeTransport: d('assets/js/shim/jquery.iframe-transport.js'),
    jqueryUiWidget: d('assets/js/shim/jquery.ui.widget.js'),
    ionRangeSlider: d('assets/js/shim/ion.rangeSlider.js'),
    "bootstrap-datepicker": d('assets/js/shim/bootstrap-datepicker.js'),
    "bootstrap-multiselect": d('assets/js/shim/bootstrap-multiselect.js'),
    jscolor: d('assets/js/shim/jscolor.js')
};

module.exports = {
    entry: getEntries(),
    /*
    externals: {
        "jquery": "jQuery",
        //jQuery: "jquery",
        //jQuery: d("assets/js/vendor/jquery"),
        //jquery: d("assets/js/vendor/jquery"),
        "window.jQuery": "jquery",
        L: "leaflet"
    },
    */
    output: {
        filename: '[name].js',
        path: d('static'),
        sourceMapFilename: '[file].map'
    },
    module: {
        //loaders: [{
        rules: [
        {
            test: /\.js$/,
            include: [d('opentreemap/frontend/js/src/')],
            use: ['babel-loader']
        /*
        }, {
            include: [shimmed["bootstrap-datepicker"], shimmed["bootstrap-multiselect"]],
            use: [ {loader: "imports-loader?bootstrap"} ]
        */
        }, {
              test: /\.(sa|sc|c)ss$/,
                use: [
                    MiniCssExtractPlugin.loader,
                    { loader: 'css-loader', options: { sourceMap: false } },
                    //{ loader: 'postcss-loader', options: { plugins: () => [autoprefixer({ browsers: ['last 2 versions'] })] } },
                    'sass-loader'
                ]
            /*
            test: /\.(css|scss)$/,
            use: [
                //MiniCssExtractPlugin.loader,
                'style-loader',
                'css-loader',
                'postcss-loader',
                'sass-loader',
            ]
            */
        }, {
            test: /\.woff($|\?)|\.woff2($|\?)|\.ttf($|\?)|\.eot($|\?)|\.svg($|\?)/,
            use: [ {loader: 'url-loader'}],
        }, {
            test: /\.(jpg|png|gif)$/,
            use: [ {loader: 'url-loader?limit=25000'} ],
        }]
    },
    resolve: {
        alias: getAliases(),
        // Look in node_modules, our shared asset 'js/vendor/' and each Django
        // app's 'js/vendor/' for modules that support a module system
        //modules: [d("assets/js/vendor"), d("node_modules")].concat(glob.sync(d('opentreemap/*/js/vendor/')))
        modules: [d("assets/js/vendor"), d("node_modules")].concat(glob.sync(d('opentreemap/*/js/vendor/')))
        //roots: [d("assets/js/vendor"), d("node_modules")].concat(glob.sync(d('opentreemap/*/js/vendor/')))
    },
    resolveLoader: {
        roots: [d("node_modules")]
    },
    optimization: {
        /*
        runtimeChunk: 'single',
        */
        splitChunks: {
            chunks: 'all',
            name: "js/treemap/base-chunk",
            minChunks: 2,
        }
    },
    plugins: [
        // Provide jquery and Leaflet as global variables, which gets rid of
        // most of our shimming needs
        // NOTE: the test configuration relies on this being the first plugin
        new Webpack.ProvidePlugin({
            jQuery: "jquery",
            $: 'jquery',
            "window.jQuery": "jquery",
            L: "leaflet",
        }),
        /*
        new Webpack.optimize.CommonsChunkPlugin({
            // Inlude the treemap/base entry module as part of the common module
            name: "js/treemap/base",

            // Chunks are moved to the common bundle if they are used in 2 or more entry bundles
            minChunks: 2,
        }),
        new MiniCssExtractPlugin({fiename: 'css/main-[chunkhash].css', {allChunks: true}),
        */
        new MiniCssExtractPlugin({filename: 'css/style-[name].css', chunkFilename: "[name].css"}),
        new BundleTracker({path: d('static'), filename: 'webpack-stats.json'})
    ]
};
