"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    otmTypeahead = require('./otmTypeahead'),
    inlineEditForm = require('./inlineEditForm'),
    mapManager = require('./mapManager'),
    plotMarker = require('./plotMarker');

// For modal dialog on jquery
require('bootstrap');

// Override typeahead from bootstrap

function addModalTrigger(element) {
    var $e = $(element);
    var $target = $($e.data('modal'));

    $e.click(function() {
        $target.modal('toggle');
    });
}

exports.init = function(options) {
    _.each(options.typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });

    addModalTrigger(options.photos.show);
    var $form = $(options.photos.form);
    $(options.photos.upload).click(function() { $form.submit(); });
    
    inlineEditForm.init(
        _.extend(options.inlineEditForm, { onSaveBefore: onSaveBefore }))

    var $editLocationButton = $(options.plotLocation.edit),
        $cancelEditLocationButton = $(options.plotLocation.cancel),
        location = options.plotLocation.location,
        map = mapManager.init({
            config: options.config,
            selector: '#map',
            center: location,
            zoom: mapManager.ZOOM_PLOT
        });

    plotMarker.init(map);
    plotMarker.place(location);

    inlineEditForm.inEditModeProperty.onValue(function (inEditMode) {
        // Form is changing to edit mode or display mode
        if (inEditMode) {
            $editLocationButton.show();
        } else { // in display mode
            $editLocationButton.hide();
            plotMarker.disableMoving();
        }
        $cancelEditLocationButton.hide();
    });

    inlineEditForm.cancelStream.onValue(function () {
        // User clicked the form's "Cancel" button. Restore plot location.
        plotMarker.place(location);
    });

    $editLocationButton.click(function () {
        // User clicked the "Move Tree" button
        $editLocationButton.hide();
        $cancelEditLocationButton.show();
        plotMarker.enableMoving();
    });

    $cancelEditLocationButton.click(function () {
        // User clicked the "Cancel Tree Move" button
        $editLocationButton.show();
        $cancelEditLocationButton.hide();
        plotMarker.disableMoving();
        plotMarker.place(location);  // Restore plot location
    });

    function onSaveBefore(data) {
        // Form is about to save its data
        if (plotMarker.wasMoved()) {
            // Add plot location to data object
            data['plot.geom'] = plotMarker.getLocation();
        }
    }

    inlineEditForm.saveOkStream.onValue(function (result) {
        // Form successfully saved its data. Update cached plot location.
        location = plotMarker.getLocation();
        // Refresh the map if appropriate
        mapManager.updateGeoRevHash(result.geoRevHash);
    });
};
