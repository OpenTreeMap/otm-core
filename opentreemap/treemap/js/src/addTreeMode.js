"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    FH = require('./fieldHelpers'),
    U = require('./utility'),
    Bacon = require('baconjs'),
    geocoder = require('./geocoder'),
    geocoderUi = require('./GeocoderUi'),
    searchEventStream = require('./searchEventStream');

var config,
    mapManager,
    plotMarker,
    onAddTree,
    onClose,  // function to call when closing mode
    $addButton,
    $address,
    $form,
    $editFields,
    $editControls,
    $validationFields,
    deactivateBus;

function init(options) {
    config = options.config;
    mapManager = options.mapManager;
    plotMarker = options.plotMarker;
    onAddTree = options.onAddTree;
    onClose = options.onClose;

    var $sidebar = options.$sidebar,
        addressInput = '#add-tree-address',
        $geolocateButton = U.$find('.geolocate', $sidebar),
        $geocodeError = U.$find('.geocode-error', $sidebar),
        $geolocateError = U.$find('.geolocate-error', $sidebar);

    $form = U.$find('#add-tree-form', $sidebar);
    $editFields = U.$find('[data-class="edit"]', $form);
    $editControls = $editFields.find('input,select');
    $validationFields = U.$find('[data-class="error"]', $form);
    $addButton = U.$find('.addBtn', $sidebar);
    $address = U.$find(addressInput, $sidebar);

    $editFields.show();
    U.$find('[data-class="display"]', $form).hide();  // Hide display fields

    // Handle setting initial tree position via geolocate button
    var geolocateStream;
    if (navigator.geolocation) {
        geolocateStream = $geolocateButton
            .asEventStream('click')
            .flatMap(geolocate);
        geolocateStream
            .filter('.coords')
            .onValue(onGeolocateSuccess);
        geolocateStream.onError(function () {
            $geolocateError.show();
        });
    } else {
        geolocateStream = Bacon.never();
        $geolocateButton.attr('disabled', true);
    }

    // Handle user dragging the marker
    var markerFirstMoveStream = plotMarker.firstMoveStream.filter(options.inMyMode);
    markerFirstMoveStream.onValue(onMarkerMoved);

    // Handle user adding a tree
    var addTreeStream = $addButton.asEventStream('click');
    addTreeStream.onValue(addTree);

    // Handle user clicking "Cancel"
    var cancelStream = U.$find('.cancelBtn', $sidebar).asEventStream('click');
    cancelStream.onValue(onClose);

    // Handle internal and external deactivation
    deactivateBus = new Bacon.Bus();
    deactivateBus.plug(cancelStream);
    deactivateBus.onValue(function () {
        // Hide/deactivate/clear everything
        plotMarker.hide();
        $address.val("");
        $editControls.val("");
    });

    // Handle setting initial tree position via address search
    var searchTriggerStream = searchEventStream({
            searchInputs: addressInput,
            searchButton: '.geocode'
        }),
        addressStream = searchTriggerStream.map(function () {
            return $(addressInput).val();
        }),
        geocodeResponseStream = geocoder(config).geocodeStream(addressStream),
        cleanupLocationFeedbackStream = Bacon.mergeAll([
            plotMarker.markerPlacedByClickStream,
            searchTriggerStream,
            geolocateStream,
            markerFirstMoveStream,
            addTreeStream,
            deactivateBus
        ]),
        geocodedLocationStream = geocoderUi({
            geocodeResponseStream: geocodeResponseStream,
            cancelGeocodeSuggestionStream: cleanupLocationFeedbackStream,
            resultTemplate: '#geocode-results-template',
            addressInput: addressInput,
            displayedResults: '#sidebar-add-tree [data-class="geocode-result"]'
        });

    cleanupLocationFeedbackStream.onValue(function hideLocationErrors() {
        $geocodeError.hide();
        $geolocateError.hide();
    });
    geocodedLocationStream.onValue(onLocationChosen);
    geocodeResponseStream.onError(function () {
        $geocodeError.show();
    });

}

// Adding a tree uses a state machine with these states and transitions:
//
// Inactive:
//     activate() -> CanPlaceMarker
//
// CanPlaceMarker:
//     onMarkerPlaced() -> CanMoveMarker
//     onLocationChosen() -> CanMoveMarker
//     cancel() -> Inactive
//     deactivate() -> Inactive
//
// CanMoveMarker:
//     onMarkerMoved() -> CanAddTree
//     cancel() -> Inactive
//     deactivate() -> Inactive
//
// CanAddTree:
//     onAddTreeSuccess() -> Inactive
//     cancel() -> Inactive
//     deactivate() -> Inactive

function activate() {
    // Let user start creating a tree (by clicking the map)
    plotMarker.hide();
    plotMarker.enablePlacing();
    $addButton.attr('disabled', true);
    $editControls.prop('disabled', true);
}

function geolocate() {
    var options = {
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: 0
    };
    var deferred = $.Deferred();
    navigator.geolocation.getCurrentPosition(deferred.resolve, deferred.reject, options);
    return Bacon.fromPromise(deferred.promise());
}

function onGeolocateSuccess(lonLat) {
    var location = U.lonLatToWebMercator(lonLat.coords.longitude, lonLat.coords.latitude);
    onLocationChosen(location);
}

function onLocationChosen(location) {
    // User has chosen an initial tree location via geocode or geolocate.
    // Show the marker (zoomed and centered), and let them drag it.
    mapManager.setCenterAndZoomIn(location, mapManager.ZOOM_PLOT);
    plotMarker.place(location);
    plotMarker.enableMoving();
    enableFormFields(false);
}

function onMarkerMoved() {
    // User moved tree for the first time. Let them edit fields.
    enableFormFields(true);
    _.defer(function () {
        $editControls.first().focus().select();
    });
}

function enableFormFields(shouldEnable) {
    $addButton.attr('disabled', !shouldEnable);
    $editControls.prop('disabled', !shouldEnable);
}

function addTree() {
    // User hit "Add Tree".
    $validationFields.hide();
    var data = FH.formToDictionary($form, $editFields);
    data['plot.geom'] = plotMarker.getLocation();

    $.ajax({
        url: config.instance.url + 'plots/',
        type: 'POST',
        contentType: "application/json",
        data: JSON.stringify(data),
        success: onAddTreeSuccess,
        error: onAddTreeError
    });
}

function onAddTreeSuccess(result) {
    // Tree was saved. Clean up and invoke callback.
    // TODO: Obey "After I add this tree" choice
    deactivateBus.push();
    mapManager.updateGeoRevHash(result.geoRevHash);
    onClose();
}

function onAddTreeError(jqXHR, textStatus, errorThrown) {
    // Tree wasn't saved. Show validation errors.
    var errorDict = jqXHR.responseJSON.validationErrors;
    _.each(errorDict, function (errorList, fieldName) {
        FH.getField($validationFields, fieldName)
            .html(errorList.join(','))
            .show();
    });
}

function deactivate() {
    // We're being deactivated by an external event
    deactivateBus.push();
}

module.exports = {
    init: init,
    activate: activate,
    deactivate: deactivate
};
