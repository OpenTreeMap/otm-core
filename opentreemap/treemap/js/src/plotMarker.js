"use strict";

// Show a marker on the map for a given location, and allow dragging it to a
// different location.

var $ = require('jquery'),
    _ = require('underscore'),
    Bacon = require('baconjs'),
    U = require('utility'),
    L = require('leaflet');

var marker,
    markerPlacedByClickBus = new Bacon.Bus(),
    firstMoveBus = new Bacon.Bus(),
    markerWasMoved,
    trackingMarker,
    config,
    lastMarkerLocation,
    map;

exports = module.exports = {

    init: function(theConfig, theMap) {
        map = theMap;
        config = theConfig;
    },

    // Allows clients to be notified when user places marker by clicking the map
    markerPlacedByClickStream: markerPlacedByClickBus,

    // Allows clients to be notified when a newly-placed marker is moved for the first time
    firstMoveStream: firstMoveBus,

    // Let user place the marker by clicking the map
    enablePlacing: function () {
        // Add a 'tracking marker' that follows the mouse, until
        // the object is placed
        if (!trackingMarker) {
            trackingMarker = L.marker({lat:0, lng:0}, {
                icon: getMarkerIcon(false)
            });

            map.on('mousemove', function(event) {
                trackingMarker.setLatLng(event.latlng);
            });
        }

        trackingMarker.addTo(map);

        map.on('click', exports.addMarkerToMap);
    },

    disablePlacing: function() {
        if (trackingMarker) {
            map.removeLayer(trackingMarker);
        }

        map.off('click', exports.addMarkerToMap);
    },

    addMarkerToMap: function(event) {
        exports.disablePlacing();
        exports.place(event.latlng);

        marker.on('dragend', onMarkerMoved);

        enableMoving();

        markerPlacedByClickBus.push();
        firstMoveBus.push();
        markerWasMoved = true;
    },

    // Put marker at the specified location (WebMercator, {x: lon, y: lat})
    place: function (location) {
        var latlng;

        if (location.x && location.y) {
            latlng = U.webMercatorToLatLng(location.x, location.y);
            latlng = L.latLng(latlng.lat, latlng.lng);
        } else {
            latlng = location;
        }

        if (marker) {
            map.removeLayer(marker);
        }

        marker = L.marker(latlng, {
            icon: getMarkerIcon(true),
            draggable: true
        });

        showViewMarker();
        markerWasMoved = false;
    },

    enableMoving: enableMoving,
    disableMoving: disableMoving,

    // Hide/deactivate/clear everything (but keep feature so its location can still be retrieved)
    hide: function () {
        if (marker) {
            lastMarkerLocation = marker.getLatLng();
            map.removeLayer(marker);
        }

        if (trackingMarker) {
            map.removeLayer(trackingMarker);
        }

        markerWasMoved = false;
    },

    // Return current marker location
    getLocation: function () {
        var latlng = marker ? marker.getLatLng() : lastMarkerLocation;

        return U.lonLatToWebMercator(latlng.lng, latlng.lat);
    },

    // Returns "True" if user dragged the marker; false otherwise
    wasMoved: function() {
        return markerWasMoved;
    }
};

// Let user move the marker by dragging it with the mouse
function enableMoving() {
    marker.dragging.enable();
    showEditMarker();
    markerWasMoved = false;
}

// Prevent user from dragging the marker
function disableMoving() {
    marker.dragging.disable();
    showViewMarker();
}

var showViewMarker = _.partial(showMarker, false),
    showEditMarker = _.partial(showMarker, true);

function showMarker(inEditMode) {
    marker.setIcon(getMarkerIcon(inEditMode));
    marker.addTo(map);
}

function getMarkerIcon(inEditMode) {
    return L.icon({
        iconUrl: config.staticUrl +
            (inEditMode ? 'img/mapmarker_editmode.png' :
                          'img/mapmarker_viewmode.png'),
        // Use half actual size to look good on IOS retina display
        iconSize: [78, 75],
        iconAnchor: [36, 62]
    });
}

function onMarkerMoved() {
    if (!markerWasMoved) {
        markerWasMoved = true;
        firstMoveBus.push();
    }
}
