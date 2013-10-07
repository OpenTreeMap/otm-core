"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    otmTypeahead = require('./otmTypeahead'),
    plotMover = require('./plotMover'),
    diameterCalculator = require('./diameterCalculator');


var mapManager,
    inlineEditForm,
    typeaheads,
    plotMarker,
    calculator;

function init(options) {
    mapManager = options.mapManager;
    inlineEditForm = options.inlineEditForm;
    typeaheads = options.typeaheads;
    plotMarker = options.plotMarker;
}

function activate() {
    _.each(typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });

    plotMover.init({
        mapManager: mapManager,
        plotMarker: plotMarker,
        inlineEditForm: inlineEditForm,
        editLocationButton: '#edit-plot-location',
        cancelEditLocationButton: '#cancel-edit-plot-location',
        location: plotMarker.getLocation()
    });

    calculator = diameterCalculator({
        formSelector: '#details-form',
        cancelStream: inlineEditForm.cancelStream,
        saveOkStream: inlineEditForm.saveOkStream
    });

}

function deactivate() {
    calculator.destroy();
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

