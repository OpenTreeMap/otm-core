"use strict";

var $ = require('jquery'),
    _ = require('underscore');

exports.init = function(options) {
    var mapManager = options.mapManager,
        plotMarker = options.plotMarker,
        inlineEditForm = options.inlineEditForm,
        $editLocationButton = $(options.editLocationButton),
        $cancelEditLocationButton = $(options.cancelEditLocationButton),
        location = options.location;

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

    exports.onSaveBefore = function(data) {
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
