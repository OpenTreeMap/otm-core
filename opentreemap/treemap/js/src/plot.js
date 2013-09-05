"use strict";

var $ = require('jquery');
var _ = require('underscore');
var otmTypeahead = require('./otmTypeahead');

var inlineEditForm = require('./inlineEditForm'),
    mapManager = require('./mapManager');

exports.init = function(options) {
    _.each(options.typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });
    inlineEditForm.init(options.inlineEditForm);

    var map = mapManager.init({
        config: options.config,
        selector: '#map',
        center: options.location,
        zoom: mapManager.ZOOM_PLOT
    });
};
