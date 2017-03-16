"use strict";

var $ = require('jquery'),
    BU = require('treemap/lib/baconUtils.js'),
    _ = require('lodash'),
    L = require('leaflet'),
    layersLib = require('treemap/lib/layers.js'),
    config = require('treemap/lib/config'),
    reverse = require('reverse');

var currentLayer = null,
    shouldZoomOnLayerChange = true;

function clearLayer(map) {
    if (currentLayer) {
        map.removeLayer(currentLayer);
    }
}

function showBoundaryGeomOnMapLayerAndZoom(map, boundaryGeoJsonLayer) {
    clearLayer(map);

    currentLayer = boundaryGeoJsonLayer;
    map.addLayer(boundaryGeoJsonLayer);

    if (shouldZoomOnLayerChange) {
        map.fitBounds(currentLayer.getBounds());
    }
}

function instanceBoundaryIdToUrl(id) {
    return reverse.boundaries_geojson({
        instance_url_name: config.instance.url_name,
        boundary_id: id
    });
}

function parseGeoJson(style, geojson) {
    var options = _.extend({
            style: function() { return style; },
            className: 'boundary-polygon'
        }, layersLib.SEARCHED_BOUNDARY_PANE_OPTION);

    var layer = L.geoJson(geojson, options),
        inner = layer.getLayers()[0],
        latLngs = inner.getLatLngs();

    // Create a polygon instead of a geoJson layer
    // to support custom area editing.
    if (1 === latLngs.length) {
        return L.polygon(latLngs[0][0], options);
    }
    return layer;
}

exports = module.exports = {
    init: function (options) {
        var map = options.map,
            idStream = options.idStream,
            boundaries = idStream
                .filter(BU.isNumber)
                .map(instanceBoundaryIdToUrl)
                .flatMap(BU.getJsonFromUrl),
            parsed = boundaries.map(parseGeoJson, options.style);

        parsed.onValue(showBoundaryGeomOnMapLayerAndZoom, map);

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

        return parsed;
    },
    getCurrentLayer: function () {
        return currentLayer;
    },
    shouldZoomOnLayerChange: function (shouldZoom) {
        shouldZoomOnLayerChange = shouldZoom;
    }
};
