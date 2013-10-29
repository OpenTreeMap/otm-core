"use strict";

var $ = require('jquery'),
    BU = require('treemap/baconUtils'),
    _ = require('underscore'),
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

    // Make overlay layer be below tiles
    $(map.getPanes().overlayPane).css('z-index', -2);

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
