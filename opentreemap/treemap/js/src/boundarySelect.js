"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    BU = require('BaconUtils'),
    _ = require('underscore'),
    OL = require('OpenLayers');

var boundaryUrlTemplate = _.template('<%= instanceUrl %>boundaries/<%= boundaryId %>/geojson/');
var geoJsonParser = new OL.Format.GeoJSON();

function addRegionLayerToMap(map, style) {
    var defaultStyle = OL.Util.extend({}, OL.Feature.Vector.style['default']);
    var layerStyle = OL.Util.extend(defaultStyle, style);

    var boundaryHighlightLayer = new OL.Layer.Vector(
        "Selected Boundary", { style: layerStyle });

    map.addLayer(boundaryHighlightLayer);
    // Push the boundary highlight layer below the tile layers
    map.setLayerIndex(boundaryHighlightLayer, 0);
    return boundaryHighlightLayer;
}

function clearRegionLayer(layer) {
    layer.removeAllFeatures();
}

function showBoundaryGeomOnMapLayerAndZoom(map, layer, boundaryGeom) {
    var polygonFeature = new OL.Feature.Vector(boundaryGeom);
    clearRegionLayer(layer);
    layer.addFeatures([polygonFeature]);
    map.zoomToExtent(boundaryGeom.getBounds());
}

function instanceBoundaryIdToUrl(instanceUrl, id) {
    return boundaryUrlTemplate({
        instanceUrl: instanceUrl,
        boundaryId: id
    });
}

exports.init = function (options) {
    var map = options.map,
        layer = addRegionLayerToMap(map, options.style),
        clearLayer = _.partial(clearRegionLayer, layer),
        idStream = options.idStream,
        geoJsonToBoundaryGeom = _.bind(geoJsonParser.parseGeometry, geoJsonParser),
        boundaries = idStream
            .filter(BU.isDefined)
            .map(instanceBoundaryIdToUrl, options.config.instance.url)
            .flatMap(BU.getJsonFromUrl);

    boundaries.map(geoJsonToBoundaryGeom)
              .onValue(showBoundaryGeomOnMapLayerAndZoom, map, layer);

    // If there is an error fetching or parsing the
    // boundary, we should clear any existing, stale
    // boundary highlight.
    boundaries.onError(clearLayer);

    // Write the error to the console to allow for
    // debugging unexpected problems parsing the GeoJSON
    // or showing the parsed geometry on the map.
    boundaries.onError(window.console.log);

    // If the id stream contains an undefined value
    // it means that the current search does not contain
    // a boundary component. In that case, we want to
    // clear any previouly highlighted area.
    idStream.filter(BU.isUndefined).onValue(clearLayer);
};
