"use strict";

// Show a marker on the map for a given location, and allow dragging it to a
// different location.

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    U = require('treemap/utility'),
    L = require('leaflet');

var marker,
    shouldUseTreeIcon,
    markerDraggingContext,
    firstMoveBus = new Bacon.Bus(),
    moveBus = new Bacon.Bus(),
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

    useTreeIcon: function(shouldUse) {
        shouldUseTreeIcon = shouldUse;
    },

    bindPopup: function(pop) {
        if (marker)
            marker.bindPopup(pop);
    },

    unbindPopup: function() {
        if (marker)
            marker.unbindPopup();
    },

    // Allows clients to be notified when a newly-placed marker is moved for the first time
    firstMoveStream: firstMoveBus,

    moveStream: moveBus.map(_.identity),

    // Let user place the marker by clicking the map
    enablePlacing: function () {
        // Add a 'tracking marker' that follows the mouse, until
        // the object is placed
        if (!trackingMarker) {
            trackingMarker = L.marker({lat:0, lng:0});

            map.on('mousemove', function(event) {
                trackingMarker.setLatLng(event.latlng);
            });
        }
        trackingMarker.setIcon(getMarkerIcon(false));
        trackingMarker.addTo(map);

        map.on('click', onMarkerPlacedByClick);
    },

    disablePlacing: function() {
        if (trackingMarker) {
            map.removeLayer(trackingMarker);
        }

        map.off('click', onMarkerPlacedByClick);
    },

    // Put marker at the specified location (WebMercator, {x: lon, y: lat})
    place: function (location) {
        // If we're tracking mouse movements, remove the tracker
        if (trackingMarker) {
            map.removeLayer(trackingMarker);
        }

        var latlng;

        if (typeof location.x !== 'undefined' &&
            typeof location.y !== 'undefined') {
            latlng = U.webMercatorToLeafletLatLng(location.x, location.y);
        } else {
            latlng = location;
        }

        if (marker) {
            marker.setLatLng(latlng);
        } else {
            marker = L.marker(latlng, {
                icon: getMarkerIcon(true)
            });
            marker.on('dragend', onMarkerMoved);
        }

        showViewMarker();
        markerWasMoved = false;
    },

    enableMoving: enableMoving,
    disableMoving: disableMoving,

    // Hide/deactivate/clear everything
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
        var latlng = exports.getLatLng();
        return U.lonLatToWebMercator(latlng.lng, latlng.lat);
    },

    getLatLng: function () {
        return marker ? marker.getLatLng() : lastMarkerLocation;
    },

    // Returns "True" if user dragged the marker; false otherwise
    wasMoved: function() {
        return markerWasMoved;
    }
};

function onMarkerPlacedByClick(event) {
    exports.disablePlacing();
    exports.place(event.latlng);

    enableMoving();
    onMarkerMoved();
}

// Let user move the marker by dragging it with the mouse
function enableMoving(options) {
    if (!options || options.needsFirstMove) {
        showMarker(true, 'animated');
        markerWasMoved = false;
    } else {
        showMarker(true);
    }

    // Normally we'd simply use:
    // marker.dragging.enable/disable
    //
    // However, the dragging context gets lost
    // somewhere between here and "disableMoving"
    //
    // Once lost we can't unbind the drag handler
    // and we're stuck. The workaround is to
    // hang on to the most recently added context
    // and disable when needed
    markerDraggingContext = marker.dragging;
    markerDraggingContext.enable();
}

// Prevent user from dragging the marker
function disableMoving() {
    if (markerDraggingContext) {
        markerDraggingContext.disable();
    }
    if (map.hasLayer(marker)) {
        showViewMarker();
    }
}

var showViewMarker = _.partial(showMarker, false, '');

function showMarker(inEditMode, className) {
    marker.setIcon(getMarkerIcon(inEditMode, className));
    marker.addTo(map);
}

function getMarkerIcon(inEditMode, className) {
    var whichIcon = shouldUseTreeIcon ? '' : 'droplet_',
        url = config.staticUrl + 'img/mapmarker_' + whichIcon +
            (inEditMode ? 'editmode.png' : 'viewmode.png');
    return L.icon({
        iconUrl: url,
        // Use half actual size to look good on IOS retina display
        iconSize: [78, 75],
        iconAnchor: [36, 62],
        className: className
    });
}

function onMarkerMoved() {
    moveBus.push(marker.getLatLng());
    if (!markerWasMoved) {
        markerWasMoved = true;
        firstMoveBus.push(marker.getLatLng());
        marker.setIcon(getMarkerIcon(true, ''));
    }
}
