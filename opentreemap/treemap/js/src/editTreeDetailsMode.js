"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    otmTypeahead = require('treemap/otmTypeahead'),
    plotMover = require('treemap/plotMover'),
    diameterCalculator = require('treemap/diameterCalculator'),
    reverseGeocodeStreamAndUpdateAddressesOnForm =
        require('treemap/reverseGeocodeStreamAndUpdateAddressesOnForm');


var formSelector = '#details-form',
    mapManager,
    inlineEditForm,
    typeaheads,
    plotMarker,
    calculator;

function init(options) {
    mapManager = options.mapManager;
    inlineEditForm = options.inlineEditForm;
    typeaheads = options.typeaheads;
    plotMarker = options.plotMarker;

    var markerMoveStream = plotMarker.moveStream.filter(options.inMyMode);
    reverseGeocodeStreamAndUpdateAddressesOnForm(
        options.config, markerMoveStream, formSelector);
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
        formSelector: formSelector,
        cancelStream: inlineEditForm.cancelStream,
        saveOkStream: inlineEditForm.saveOkStream
    });

}

function deactivate() {
    calculator.destroy();
    inlineEditForm.cancel();
}

function onSaveBefore(data) {
    plotMover.onSaveBefore(data);
}

module.exports = {
    name: 'editTreeDetails',
    init: init,
    activate: activate,
    deactivate: deactivate,
    onSaveBefore: onSaveBefore
};
