"use strict";

var webpack = require('webpack'),
    config = require('./webpack.common.config.js');

// Only use the test entry file
config.entry = {
    'js/testRunner': __dirname + '/assets/tests/testRunner.js'
};
// Put a dummy value in place of the django reverse module in test mode
config.externals = {
    reverse: "undefined"
};

// We only want the ProvidePlugin for tests
config.plugins = [config.plugins[0]];

module.exports = config;
