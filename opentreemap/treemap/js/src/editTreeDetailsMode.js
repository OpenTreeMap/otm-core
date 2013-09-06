"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    otmTypeahead = require('./otmTypeahead'),
    plotMover = require('./plotMover');

var mapManager,
    inlineEditForm,
    plotMarker;

function init(options) {
    mapManager = options.mapManager;
    inlineEditForm = options.inlineEditForm;
    plotMarker = options.plotMarker;

    _.each(options.typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });
}

function activate() {
    plotMover.init({
        mapManager: mapManager,
        plotMarker: plotMarker,
        inlineEditForm: inlineEditForm,
        editLocationButton: '#edit-plot-location',
        cancelEditLocationButton: '#cancel-edit-plot-location',
        location: plotMarker.getLocation()
    })
}

function deactivate() {
}

function onSaveBefore(data) {
    plotMover.onSaveBefore(data);
}

module.exports = {
    init: init,
    activate: activate,
    deactivate: deactivate,
    onSaveBefore: onSaveBefore
};

