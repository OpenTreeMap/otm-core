"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    OL = require('OpenLayers'),
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
    vectorLayer,
    pointControl,
    dragControl,
    pointFeature,
    userHasMovedTree;

function init(options) {
    config = options.config;
    map = options.map;
    onAddTree = options.onAddTree;
    onClose = options.onClose;
    $sidebar = options.$sidebar;

    vectorLayer = new OL.Layer.Vector(
        "Vector Layer",
        { renderers: OL.Layer.Vector.prototype.renderers });

    pointControl = new OL.Control.DrawFeature(
        vectorLayer,
        OL.Handler.Point,
        { 'featureAdded': onMarkerPlaced });

    dragControl = new OL.Control.DragFeature(vectorLayer);
    dragControl.onDrag = onMarkerMoved;

    map.addLayer(vectorLayer);
    map.addControl(pointControl);
    map.addControl(dragControl);

    $form = U.$find('#add-tree-form', $sidebar);
    $editFields = U.$find('[data-class="edit"]', $form);
    $editControls = $editFields.find('input,select');
    $displayFields = U.$find('[data-class="display"]', $form);
    $validationFields = U.$find('[data-class="error"]', $form);
    $addButton = U.$find('.saveBtn', $sidebar).click(addTree);
    U.$find('.cancelBtn', $sidebar).click(cancel);

    $editFields.css('display', 'inline-block');
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
    vectorLayer.display(true);
    pointControl.activate();
    $addButton.attr('disabled', true);
    $editControls.prop('disabled', true);
    userHasMovedTree = false;
}

function onMarkerPlaced(feature) {
    // User clicked the map. Let them drag the tree position.
    pointFeature = feature;
    pointControl.deactivate();
    dragControl.activate();
}

function onMarkerMoved(feature) {
    // User moved the tree location. Remember feature.
    if (!userHasMovedTree) {
        // This is the first move. Let them edit fields.
        userHasMovedTree = true;
        $addButton.attr('disabled', false);
        $editControls.prop('disabled', false);
        setTimeout(function () {
            $editControls.first().focus().select();
        }, 0);
    }
}

function addTree() {
    // User hit "Add Tree".
    $validationFields.hide();
    var data = FH.formToDictionary($form, $editFields);
    data['plot.geom'] = {
        x: pointFeature.geometry.x,
        y: pointFeature.geometry.y
    };

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
            .css('display', 'inline-block');
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
    pointControl.deactivate();
    dragControl.deactivate();
    vectorLayer.display(false);
    if (pointFeature)
        pointFeature.destroy();
    $editControls.val("");
}

module.exports = {
    init: init,
    activate: activate,
    deactivate: deactivate
};
