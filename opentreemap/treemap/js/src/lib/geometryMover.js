"use strict";

// Manage view/edit modes for plot location.
// In edit mode, user can change the plot location by dragging the marker.

var $ = require('jquery'),
    _ = require('lodash'),
    polylineEditor = require('treemap/lib/polylineEditor.js'),
    format = require('util').format;

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
        }
        $cancelEditLocationButton.hide();
    });

    inlineEditForm.cancelStream.onValue(function () {
        obj.disable({isCancel: true});
    });

    $editLocationButton.on('click', function () {
        // User clicked the "Move Location" button
        $editLocationButton.hide();
        $cancelEditLocationButton.show();
        obj.enable();
    });

    $cancelEditLocationButton.on('click', function () {
        // User clicked the "Cancel Move Location" button
        $editLocationButton.show();
        $cancelEditLocationButton.hide();
        obj.disable({isCancel: true});
    });

    inlineEditForm
        .saveOkStream
        .map('.responseData')
        .onValue(function (responseData) {
            obj.onSaveOk(responseData.feature);
            obj.disable({isCancel: false});
            // Refresh the map if needed
            options.mapManager.updateRevHashes(responseData);
        });
}

function extendBase(overrides) {
    var _isEnabled = false,
        obj = _.extend({
            onSaveBefore: _.noop,
            onSaveOk: _.noop,
            onCancel: _.noop,
            enable: _.noop,
            disable: _.noop,
            isEnabled: function () {
                return _isEnabled;
            }
        }, overrides);

    var enable = _.bind(obj.enable, obj),
        disable = _.bind(obj.disable, obj);

    obj.enable = function () {
        enable();
        _isEnabled = true;
    };

    obj.disable = function (options) {
        disable(options);
        _isEnabled = false;
    };

    return obj;
}

exports.plotMover = function(options) {
    var obj = extendBase({
        onSaveBefore: function (data) {
            if (this.plotMarker.wasMoved()) {
                // Add plot location to data object
                data['plot.geom'] = this.plotMarker.getLocation();
            }
        },

        onSaveOk: function (feature) {
            var wasInPmf = $('#containing-polygonalmapfeature').length > 0,
                isNowInPmf = feature.containing_polygonalmapfeature;
            if (this.plotMarker.wasMoved() && (wasInPmf || isNowInPmf)) {
                window.location.reload();
            } else {
                // Form successfully saved its data. Update cached location.
                this.location = this.plotMarker.getLocation();
            }
        },

        disable: function (options) {
            if (options && options.isCancel) {
                this.plotMarker.place(this.location);
            }
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
    var obj = extendBase({

        onSaveBefore: function (data) {
            var points = this.editor.getPoints();
            if (!_.isNull(points)) {
                data[format('%s.polygon', options.resourceType)] = {polygon: points};
            }
        },

        onSaveOk: function (feature) {
            var didContainPlots = $('#contained-plots').length > 0,
                nowContainsPlots = feature.contained_plots.length > 0,
                points;
            if (this.editor.hasMoved(this.location) &&
                (didContainPlots || nowContainsPlots)) {
                window.location.reload();
            } else {
                points = this.editor.getPoints();
                if (!_.isNull(points)) {
                    this.location = this.editor.getPoints();
                }
            }
        },

        disable: function (options) {
            this.editor.removeAreaPolygon(options.isCancel);
        },

        enable: function () {
            this.editor.enableAreaPolygon({points: this.location});
        }
    });

    obj.editor = polylineEditor({mapManager: options.mapManager});
    obj.location = options.location.polygon;
    init(obj, options);
    return obj;
};
