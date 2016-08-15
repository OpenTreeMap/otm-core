"use strict";

var $ = require('jquery'),
    mapFeatureDelete = require('treemap/lib/mapFeatureDelete.js'),
    mapFeatureUdf = require('treemap/lib/mapFeatureUdf.js');

exports.init = function(form) {
mapFeatureUdf.init(form);
mapFeatureDelete.init();
};