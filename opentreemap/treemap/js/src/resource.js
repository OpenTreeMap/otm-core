"use strict";

var $ = require('jquery'),
    mapFeatureUdf = require('treemap/mapFeatureUdf');

// Placed onto the jquery object
require('bootstrap-datepicker');

exports.init = function(options) {
    var form = options.form;
    mapFeatureUdf.init(form);

    $('[data-date-format]').datepicker();
};
