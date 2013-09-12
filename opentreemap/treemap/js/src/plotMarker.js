"use strict";

// Show a marker on the map for a given location, and allow dragging it to a
// different location.

var $ = require('jquery'),
    Bacon = require('baconjs'),
    OL = require('OpenLayers');

var vectorLayer,
    pointControl,
    dragControl,
    markerFeature,
    markerPlacedByClickBus = new Bacon.Bus(),
    firstMoveBus = new Bacon.Bus(),
    markerWasMoved;


module.exports = {

    init: function(map) {
        function onMarkerPlaced(feature) {
            markerFeature = feature;
            pointControl.deactivate();
            enableMoving();
            markerPlacedByClickBus.push();
            markerWasMoved = false;
        }

        function onMarkerMoved(feature) {
            if (!markerWasMoved) {
                markerWasMoved = true;
                firstMoveBus.push();
            }
        }

        vectorLayer = new OL.Layer.Vector(
            "Vector Layer",
            { renderers: OL.Layer.Vector.prototype.renderers });

        pointControl = new OL.Control.DrawFeature(
            vectorLayer,
            OL.Handler.Point, { 'featureAdded': onMarkerPlaced }
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
    // TODO: Use a real well-designed marker (and remove this verbose style definition)
    markerFeature.style = {
        strokeColor: '#00ff00',
        fillColor: '#77ff77',
        cursor: "inherit",
        fillOpacity: 0.4,
        pointRadius: 6,
        strokeDashstyle: "solid",
        strokeOpacity: 1,
        strokeWidth: 1
    };
    vectorLayer.redraw();
}

// Prevent user from dragging the marker
function disableMoving() {
    dragControl.deactivate();
    // TODO: Use a real well-designed marker (and remove this verbose style definition)
    markerFeature.style = {
        strokeColor: '#ee9900',
        fillColor: '#ee9900',
        cursor: "inherit",
        fillOpacity: 0.4,
        pointRadius: 6,
        strokeDashstyle: "solid",
        strokeOpacity: 1,
        strokeWidth: 1
    };
    vectorLayer.redraw();
    markerWasMoved = false;
}
