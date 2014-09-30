"use strict";

var $ = require('jquery'),
    BU = require('treemap/baconUtils'),
    _ = require('lodash'),
    L = require('leaflet');

var boundaryUrlTemplate = _.template('<%= instanceUrl %>boundaries/<%= boundaryId %>/geojson/');
var currentLayer = null;

function clearLayer(map) {
    if (currentLayer) {
        map.removeLayer(currentLayer);
    }
}

function showBoundaryGeomOnMapLayerAndZoom(map, boundaryGeom) {
    clearLayer(map);

    // We want to put the boundary polygon below the plot tiles
    // so that plots will display and select normally.
    // But in Leaflet < 0.8 all polygon layers go in the "overlay pane",
    // so our only choice is to set the z-index of the entire overlay pane.
    // That's not great since we might want other polygons on the map,
    // *above* the plot tiles.
    // TODO: When we switch to Leaflet 0.8, make a separate pane to contain
    // the boundary polygon, with a permanent z-index.
    map.getPanes().overlayPane.style.zIndex = -2;

    currentLayer = boundaryGeom;

    map.addLayer(boundaryGeom);
    map.fitBounds(boundaryGeom.getBounds());
}

function instanceBoundaryIdToUrl(instanceUrl, id) {
    return boundaryUrlTemplate({
        instanceUrl: instanceUrl,
        boundaryId: id
    });
}

function parseGeoJson(style, geojson) {
    return L.geoJson(geojson, {
        style: function() { return style; }
    });
}

exports.init = function (options) {
    var map = options.map,
        idStream = options.idStream,
        boundaries = idStream
            .filter(BU.isDefined)
            .map(instanceBoundaryIdToUrl, options.config.instance.url)
            .flatMap(BU.getJsonFromUrl);

    boundaries.map(parseGeoJson, options.style)
        .onValue(showBoundaryGeomOnMapLayerAndZoom, map);

    // If there is an error fetching or parsing the
    // boundary, we should clear any existing, stale
    // boundary highlight.
    boundaries.onError(clearLayer, map);

    // Write the error to the console to allow for
    // debugging unexpected problems parsing the GeoJSON
    // or showing the parsed geometry on the map.
    boundaries.onError(window.console.log);

    // If the id stream contains an undefined value
    // it means that the current search does not contain
    // a boundary component. In that case, we want to
    // clear any previouly highlighted area.
    idStream.filter(BU.isUndefined).onValue(clearLayer, map);
};
