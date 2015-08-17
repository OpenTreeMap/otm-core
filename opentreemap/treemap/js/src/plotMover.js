"use strict";

// Manage view/edit modes for plot location.
// In edit mode, user can change the plot location by dragging the marker.

var $ = require('jquery'),
    _ = require('lodash'),
    polylineEditor = require('treemap/polylineEditor'),
    format = require('util').format;

require('leafletEditablePolyline');

function init(obj, options) {
    var inlineEditForm = options.inlineEditForm,
        $editLocationButton = $(options.editLocationButton),
        $cancelEditLocationButton = $(options.cancelEditLocationButton);

    inlineEditForm.inEditModeProperty.onValue(function (inEditMode) {
        // Form is changing to edit mode or display mode
        if (inEditMode) {
            $editLocationButton.show();
        } else { // in display mode
            $editLocationButton.hide();
            obj.disable();
        }
        $cancelEditLocationButton.hide();
    });

    inlineEditForm.cancelStream.onValue(function () {
        obj.onCancel();
    });

    $editLocationButton.click(function () {
        // User clicked the "Move Location" button
        $editLocationButton.hide();
        $cancelEditLocationButton.show();
        obj.enable();
    });

    $cancelEditLocationButton.click(function () {
        // User clicked the "Cancel Move Location" button
        $editLocationButton.show();
        $cancelEditLocationButton.hide();
        obj.onCancel();
        obj.disable();
    });

    inlineEditForm
        .saveOkStream
        .map('.responseData.geoRevHash')
        .onValue(function (georev) {
            // Refresh the map if needed
            options.mapManager.updateGeoRevHash(georev);
        });
}

var base = exports.base = function () {
    var obj = {
        onSaveBefore: _.noop,
        onSaveAfter: _.noop,
        onCancel: _.noop,
        enable: _.noop,
        disable: _.noop
    };

    return obj;
};

exports.plotMover = function(options) {
    var obj = _.extend(base(), {
        onSaveBefore: function (data) {
            if (this.plotMarker.wasMoved()) {
                // Add plot location to data object
                data['plot.geom'] = this.plotMarker.getLocation();
            }
        },

        onSaveAfter: function (data) {
            var wasInPmf = $('#containing-polygonalmapfeature').length > 0,
                isNowInPmf = data.feature.containing_polygonalmapfeature;
            if (this.plotMarker.wasMoved() && (wasInPmf || isNowInPmf)) {
                window.location.reload();
            } else {
                // Form successfully saved its data. Update cached location.
                this.location = this.plotMarker.getLocation();
            }
        },

        onCancel: function () {
            // User clicked the inlineEditForm's "Cancel" button (distinct from the
            // "Cancel Tree Move" button managed by this module). Restore plot location.
            this.plotMarker.place(this.location);
        },

        disable: function () {
            this.plotMarker.disableMoving();
        },
        enable: function () {
            this.plotMarker.enableMoving();
        }
    });

    init(obj, options);
    obj.location = options.location.point;
    obj.plotMarker = options.plotMarker;
    obj.plotMarker.place(obj.location);
    return obj;
};


exports.polygonMover = function (options) {
    var obj = _.extend(base(), {

        onSaveBefore: function (data) {
            var points = this.editor.getPoints();
            if (!_.isNull(points)) {
                data[format('%s.polygon', options.resourceType)] = {polygon: points};
            }
        },

        onSaveAfter: function (data) {
            var didContainPlots = $('#contained-plots').length > 0,
                nowContainsPlots = data.feature.contained_plots.length > 0,
                points;
            if (this.editor.hasMoved(this.location) &&
                (didContainPlots || nowContainsPlots)) {
                window.location.reload();
            } else {
                points = this.editor.getPoints();
                if (!_.isNull(points)) {
                    this.location = this.editor.getPoints();
                }
                this.editor.removeAreaPolygon();
            }
        },

        disable: function () {
            this.editor.removeAreaPolygon();
        },

        enable: function () {
            this.editor.enableAreaPolygon({points: this.location});
        }
    });

    obj.editor = polylineEditor({config: options.config,
                                 mapManager: options.mapManager});
    obj.location = options.location.polygon;
    init(obj, options);
    return obj;
};
