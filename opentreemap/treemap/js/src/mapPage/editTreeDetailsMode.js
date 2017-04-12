"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    toastr = require('toastr'),
    otmTypeahead = require('treemap/lib/otmTypeahead.js'),
    geometryMover = require('treemap/lib/geometryMover.js'),
    diameterCalculator = require('treemap/lib/diameterCalculator.js'),
    plotMarker = require('treemap/lib/plotMarker.js'),
    reverseGeocodeStreamAndUpdateAddressesOnForm =
        require('treemap/lib/reverseGeocodeStreamAndUpdateAddressesOnForm.js');

var dom = {
    form: '#details-form',
    ecoBenefits: '.benefit-values',
    mapFeatureAccordion: '#map-feature-accordion',
    treeDetailAccordion: '#tree-detail'
};

var mapManager,
    inlineEditForm,
    typeaheads,
    calculator,
    currentPlotMover;

function init(options) {
    mapManager = options.mapManager;
    inlineEditForm = options.inlineEditForm;
    typeaheads = options.typeaheads;

    inlineEditForm.inEditModeProperty.onValue(function (inEditMode) {
        $(dom.ecoBenefits).toggle(!inEditMode);
    });

    var markerMoveStream = plotMarker.moveStream.filter(options.inMyMode);
    reverseGeocodeStreamAndUpdateAddressesOnForm(markerMoveStream, dom.form);
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

    // For full-screen mobile view, set class on body when starting/canceling
    // plot move mode
    $('#edit-plot-location,#cancel-edit-plot-location').on('click', function () {
        $('body').toggleClass('feature-move');
        mapManager.map.invalidateSize();
    });

    $('#done-edit-plot-location').on('click', function() {
        $('#edit-plot-location').show();
        $('#cancel-edit-plot-location').hide();
        currentPlotMover.disable();
        $('body').toggleClass('feature-move');
        mapManager.map.invalidateSize();
    });
}

function deactivate(options) {
    calculator.destroy();
    inlineEditForm.cancel();
    mapManager.map.off('click', onClick);
    var keepSelection = options && options.keepSelection;
    if (!keepSelection) {
        clearSelection();
    }
}

function clearSelection() {
    $(dom.mapFeatureAccordion).html('');
    $(dom.treeDetailAccordion).collapse('hide');
    $('body').removeClass('feature-selected');  // for mobile
    plotMarker.hide();
}

function onSaveBefore(data) {
    if (currentPlotMover) {
        currentPlotMover.onSaveBefore(data);
    }
}

module.exports = {
    name: 'editTreeDetails',
    hideSearch: true,
    init: init,
    activate: activate,
    deactivate: deactivate,
    onSaveBefore: onSaveBefore,
    lockOnActivate: true
};
