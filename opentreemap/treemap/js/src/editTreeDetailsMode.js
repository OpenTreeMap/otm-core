"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    toastr = require('toastr'),
    otmTypeahead = require('treemap/otmTypeahead'),
    geometryMover = require('treemap/geometryMover'),
    diameterCalculator = require('treemap/diameterCalculator'),
    reverseGeocodeStreamAndUpdateAddressesOnForm =
        require('treemap/reverseGeocodeStreamAndUpdateAddressesOnForm');

var dom = {
    form: '#details-form',
    ecoBenefits: '.benefit-values'
};

var mapManager,
    inlineEditForm,
    typeaheads,
    plotMarker,
    calculator,
    currentPlotMover;

function init(options) {
    mapManager = options.mapManager;
    inlineEditForm = options.inlineEditForm;
    typeaheads = options.typeaheads;
    plotMarker = options.plotMarker;

    inlineEditForm.inEditModeProperty.onValue(function (inEditMode) {
        $(dom.ecoBenefits).toggle(!inEditMode);
    });

    var markerMoveStream = plotMarker.moveStream.filter(options.inMyMode);
    reverseGeocodeStreamAndUpdateAddressesOnForm(
        options.config, markerMoveStream, dom.form);
}

function onClick(e) { 
    toastr.options = {
        "positionClass": "toast-bottom-left",
        "timeOut": "3000"
    };
    toastr.info('Click "Save" or "Cancel" to end your Quick Edit session.');
}

function activate() {
    otmTypeahead.bulkCreate(typeaheads);

    currentPlotMover = geometryMover.plotMover({
        mapManager: mapManager,
        plotMarker: plotMarker,
        inlineEditForm: inlineEditForm,
        editLocationButton: '#edit-plot-location',
        cancelEditLocationButton: '#cancel-edit-plot-location',
        location: {point: plotMarker.getLocation()}
    });

    calculator = diameterCalculator({
        formSelector: dom.form,
        cancelStream: inlineEditForm.cancelStream,
        saveOkStream: inlineEditForm.saveOkStream
    });

    mapManager.map.on('click', onClick);

}

function deactivate() {
    calculator.destroy();
    inlineEditForm.cancel();

    mapManager.map.off('click', onClick);
}

function onSaveBefore(data) {
    if (currentPlotMover) {
        currentPlotMover.onSaveBefore(data);
    }
}

module.exports = {
    name: 'editTreeDetails',
    init: init,
    activate: activate,
    deactivate: deactivate,
    onSaveBefore: onSaveBefore,
    lockOnActivate: true
};
