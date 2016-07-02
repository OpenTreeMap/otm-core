"use strict";

var $ = require('jquery'),
    mapFeature = require('treemap/lib/mapFeature.js'),
    mapFeatureDelete = require('treemap/lib/mapFeatureDelete.js'),
    mapFeatureUdf = require('treemap/lib/mapFeatureUdf.js');

// Placed onto the jquery object
require('bootstrap-datepicker');

var form = mapFeature.init().inlineEditForm;
mapFeatureUdf.init(form);
mapFeatureDelete.init();
$('[data-date-format]').datepicker();
