"use strict";

var $ = require('jquery'),
    mapFeatureDelete = require('treemap/plotDelete'),
    mapFeatureUdf = require('treemap/mapFeatureUdf');

// Placed onto the jquery object
require('bootstrap-datepicker');

exports.init = function(options) {
    mapFeatureUdf.init(options.form);
    mapFeatureDelete.init(options);
    $('[data-date-format]').datepicker();
};
