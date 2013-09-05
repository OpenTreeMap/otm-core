"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    plotMarker = require('./plotMarker'),
    FH = require('./fieldHelpers'),
    U = require('./utility');

var config,
    map,
    onAddTree,
    onClose,  // function to call when closing mode
    $sidebar,
    $addButton,
    $form,
    $editFields,
    $editControls,
    $displayFields,
    $validationFields,
    markerMovedStream;

function init(options) {
    config = options.config;
    map = options.map;
    onAddTree = options.onAddTree;
    onClose = options.onClose;
    $sidebar = options.$sidebar;

    plotMarker.init(map);
    plotMarker.firstMoveStream.onValue(onMarkerMoved);

    $form = U.$find('#add-tree-form', $sidebar);
    $editFields = U.$find('[data-class="edit"]', $form);
    $editControls = $editFields.find('input,select');
    $displayFields = U.$find('[data-class="display"]', $form);
    $validationFields = U.$find('[data-class="error"]', $form);
    $addButton = U.$find('.saveBtn', $sidebar).click(addTree);
    U.$find('.cancelBtn', $sidebar).click(cancel);

    $editFields.show();
    $displayFields.hide();
    $validationFields.hide();
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
    plotMarker.enablePlacing();
    $addButton.attr('disabled', true);
    $editControls.prop('disabled', true);
}

function onMarkerMoved() {
    // User moved tree for the first time. Let them edit fields.
    $addButton.attr('disabled', false);
    $editControls.prop('disabled', false);
    setTimeout(function () {
        $editControls.first().focus().select();
    }, 0);
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
    onAddTree(result.geoRevHash);
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
