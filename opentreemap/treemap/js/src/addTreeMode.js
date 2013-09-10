"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    FH = require('./fieldHelpers'),
    U = require('./utility');

var config,
    mapManager,
    plotMarker,
    onAddTree,
    onClose,  // function to call when closing mode
    $sidebar,
    $addButton,
    $address,
    $geocodeError,
    $geolocateError,
    $form,
    $editFields,
    $editControls,
    $displayFields,
    $validationFields;

function init(options) {
    config = options.config;
    mapManager = options.mapManager;
    plotMarker = options.plotMarker;
    onAddTree = options.onAddTree;
    onClose = options.onClose;
    $sidebar = options.$sidebar;

    plotMarker.firstMoveStream
        .filter(options.inMyMode)
        .onValue(onMarkerMoved);

    $form = U.$find('#add-tree-form', $sidebar);
    $editFields = U.$find('[data-class="edit"]', $form);
    $editControls = $editFields.find('input,select');
    $displayFields = U.$find('[data-class="display"]', $form);
    $validationFields = U.$find('[data-class="error"]', $form);
    $addButton = U.$find('.saveBtn', $sidebar).click(addTree);
    $address = U.$find('#add-tree-address', $sidebar);
    $geocodeError = U.$find('.geocode-error', $sidebar);
    $geolocateError = U.$find('geolocate-error', $sidebar);
    U.$find('.geocode', $sidebar).click(geocode);
    U.$find('.geolocate', $sidebar).click(geolocate);
    U.$find('.cancelBtn', $sidebar).click(cancel);

    $editFields.show();
    $displayFields.hide();
}

// Adding a tree uses a state machine with these states and transitions:
//
// Inactive:
//     activate() -> CanPlaceMarker
//
// CanPlaceMarker:
//     onMarkerPlaced() -> CanMoveMarker
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

function geocode()
{
}

function geolocate()
{
    if (navigator.geolocation)
    {
        hideLocationErrors();
        var options = {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
        };
        navigator.geolocation.getCurrentPosition(onSuccess, onError, options);
    }
    else {
        onError();
    }

    function onSuccess(lonLat) {
        var location = U.lonLatToWebMercator(lonLat.coords.longitude, lonLat.coords.latitude)
        plotMarker.place(location);
        plotMarker.enableMoving();
        enableStep2(false);
    }

    function onError(error) {
        $geolocateError.show();
    }
}

function hideLocationErrors() {
    $geocodeError.hide();
    $geolocateError.hide();
}

function onMarkerMoved() {
    // User moved tree for the first time. Let them edit fields.
    enableStep2(true);
    _.defer(function () {
        $editControls.first().focus().select();
    });
}

function enableStep2(shouldEnable) {
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
    // Tree was saved. Clean up and invoke callbacks.
    // TODO: Obey "After I add this tree" choice
    cleanup();
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

function cancel() {
    // User hit "Cancel". Clean up and invoke callback.
    cleanup();
    onClose();
}

function deactivate() {
    // We're being deactivated by an external event
    cleanup();
}

function cleanup() {
    // Hide/deactivate/clear everything
    plotMarker.hide();
    $editControls.val("");
}

module.exports = {
    init: init,
    activate: activate,
    deactivate: deactivate
};
