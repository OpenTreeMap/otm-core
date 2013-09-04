"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    OL = require('OpenLayers');

var vectorLayer,
    pointControl,
    dragControl,
    markerFeature,
    firstMoveBus = new Bacon.Bus(),
    markerWasMoved = false;


module.exports = {

    init: function(map) {
        function onMarkerPlaced(feature) {
            markerFeature = feature;
            pointControl.deactivate();
            dragControl.activate();
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

    firstMoveStream: firstMoveBus,

    enablePlacing: function () {
        vectorLayer.display(true);
        pointControl.activate();
    },

    place: function (location) {
        if (markerFeature) {
            markerFeature.destroy();
        }
        markerFeature = new OL.Feature.Vector(
            new OL.Geometry.Point(location.x, location.y));
        vectorLayer.addFeatures(markerFeature);
        vectorLayer.display(true);
    },

    enableMoving: function () {
        dragControl.activate();
//        markerFeature.style = {
//            strokeColor: '#00ff00',
//            fillColor: '#77ff77'
//        };
    },

    disableMoving: function () {
        dragControl.deactivate();
//        markerFeature.style = {
//            strokeColor: '#ff0000',
//            fillColor: '#ff7777'
//        };
        markerWasMoved = false;
    },

    hide: function () {
        // Hide/deactivate/clear everything
        pointControl.deactivate();
        dragControl.deactivate();
        vectorLayer.display(false);
        if (markerFeature)
            markerFeature.destroy();
        markerWasMoved = false;
    },

    getLocation: function () {
        return {
            x: markerFeature.geometry.x,
            y: markerFeature.geometry.y
        };
    },

    wasMoved: function() {
        return markerWasMoved;
    }
};