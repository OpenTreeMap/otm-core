"use strict";

// Show a marker on the map for a given location, and allow dragging it to a
// different location.

var $ = require('jquery'),
    _ = require('underscore'),
    Bacon = require('baconjs'),
    OL = require('OpenLayers');

var vectorLayer,
    pointControl,
    dragControl,
    markerFeature,
    markerPlacedByClickBus = new Bacon.Bus(),
    firstMoveBus = new Bacon.Bus(),
    markerWasMoved,
    config;


module.exports = {

    init: function(theConfig, map) {
        config = theConfig;

        function onMarkerPlaced(feature) {
            markerFeature = feature;
            pointControl.deactivate();
            enableMoving();
            markerPlacedByClickBus.push();
            firstMoveBus.push();
            markerWasMoved = true;
        }

        function onMarkerMoved(feature) {
            if (!markerWasMoved) {
                markerWasMoved = true;
                firstMoveBus.push();
            }
        }

        vectorLayer = new OL.Layer.Vector(
            "Vector Layer",
            { renderers: OL.Layer.Vector.prototype.renderers,
              displayInLayerSwitcher: false });

        var pointControlFeature = new OL.Feature.Vector(new OL.Geometry.Point());
        pointControlFeature.style = getMarkerStyle(true);
        pointControl = new OL.Control.DrawFeature(
            vectorLayer,
            OL.Handler.Point,
            {
                'featureAdded': onMarkerPlaced,
                'handlerOptions': { point: pointControlFeature }
            }
        );

        dragControl = new OL.Control.DragFeature(vectorLayer);
        dragControl.onComplete = onMarkerMoved;

        map.addLayer(vectorLayer);
        map.addControl(pointControl);
        map.addControl(dragControl);
    },

    // Allows clients to be notified when user places marker by clicking the map
    markerPlacedByClickStream: markerPlacedByClickBus,

    // Allows clients to be notified when a newly-placed marker is moved for the first time
    firstMoveStream: firstMoveBus,

    // Let user place the marker by clicking the map
    enablePlacing: function () {
        vectorLayer.display(true);
        pointControl.activate();
    },

    // Put marker at the specified location (WebMercator, {x: lon, y: lat})
    place: function (location) {
        pointControl.deactivate();
        if (markerFeature) {
            markerFeature.destroy();
        }
        markerFeature = new OL.Feature.Vector(
            new OL.Geometry.Point(location.x, location.y));
        vectorLayer.addFeatures(markerFeature);
        vectorLayer.display(true);
        showViewMarker();
        markerWasMoved = false;
    },

    enableMoving: enableMoving,
    disableMoving: disableMoving,

    // Hide/deactivate/clear everything (but keep feature so its location can still be retrieved)
    hide: function () {
        pointControl.deactivate();
        dragControl.deactivate();
        vectorLayer.removeAllFeatures();
        vectorLayer.display(false);
        markerWasMoved = false;
    },

    // Return current marker location
    getLocation: function () {
        return {
            x: markerFeature.geometry.x,
            y: markerFeature.geometry.y
        };
    },

    // Returns "True" if user dragged the marker; false otherwise
    wasMoved: function() {
        return markerWasMoved;
    }
};

// Let user move the marker by dragging it with the mouse
function enableMoving() {
    dragControl.activate();
    showEditMarker();
    markerWasMoved = false;
}

// Prevent user from dragging the marker
function disableMoving() {
    dragControl.deactivate();
    showViewMarker();
}

var showViewMarker = _.partial(showMarker, false),
    showEditMarker = _.partial(showMarker, true);

function showMarker(inEditMode) {
    markerFeature.style = getMarkerStyle(inEditMode);
    vectorLayer.redraw();
}

function getMarkerStyle(inEditMode) {
    return {
        externalGraphic: config.staticUrl +
            (inEditMode ? 'img/mapmarker_editmode.png' :
                          'img/mapmarker_viewmode.png'),
        // Use half actual size to look good on IOS retina display
        graphicHeight: 75,
        graphicWidth: 78,
        graphicXOffset: -36,
        graphicYOffset: -62
    };
}
