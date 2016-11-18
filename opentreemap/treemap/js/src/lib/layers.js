"use strict";

var $ = require("jquery"),
    _ = require("lodash"),
    L = require('leaflet'),
    urlLib = require('url'),
    Search = require("treemap/lib/search.js"),
    config = require("treemap/lib/config.js"),
    format = require('util').format,

    MAX_ZOOM_OPTION = exports.MAX_ZOOM_OPTION = {maxZoom: 21},
    // Min zoom level for detail layers
    MIN_ZOOM_OPTION = exports.MIN_ZOOM_OPTION = {minZoom: 15},

    // Make a separate pane for the base map and for the searched boundary polygon,
    // so we can show the polygon between the base map and the other tiles.
    // (see CSS for z-index of .leaflet-base-pane and .leaflet-searched-boundary-pane)
    baseMapPaneName = 'base-map',
    searchedBoundaryPaneName = 'searched-boundary',
    BASE_PANE_OPTION = exports.BASE_PANE_OPTION = {pane: baseMapPaneName},
    SEARCHED_BOUNDARY_PANE_OPTION = exports.SEARCHED_BOUNDARY_PANE_OPTION = {pane: searchedBoundaryPaneName},

    // Control stacking of tile layers within the Leaflet tile pane

    // Outlines of named boundaries (treemap.Boundary model)
    BOUNDARY_LAYER_OPTION = {zIndex: 1},

    // Custom-configured layers for individual treemaps (e.g. canopy layer)
    CUSTOM_LAYER_OPTION = {zIndex: 2},

    // Canopy percentages chloropleth layer (for e.g. patreemap)
    CANOPY_BOUNDARY_LAYER_OPTION = {zIndex: 3, opacity: 0.75},

    // Tree dots (all and searched) and their UTF grids
    FEATURE_LAYER_OPTION = {zIndex: 4};

////////////////////////////////////////////////
// public functions
////////////////////////////////////////////////

exports.initPanes = function (map) {
    map.createPane(baseMapPaneName);
    map.createPane(searchedBoundaryPaneName);
};

exports.createBoundariesTileLayer = function () {
    // we will never update boundaries based on a revision, so
    // safe to use the same url permanently.
    var revToUrl = getUrlMaker('treemap_boundary', 'png'),
        url = revToUrl(config.instance.geoRevHash),
        options = _.extend({}, MAX_ZOOM_OPTION, MIN_ZOOM_OPTION, BOUNDARY_LAYER_OPTION);
    return L.tileLayer(url, options);
};

exports.getCanopyBoundariesTileLayerUrl = function(tilerArgs) {
    var revToUrl = getUrlMaker('treemap_canopy_boundary', 'png', tilerArgs);
    return revToUrl(config.instance.geoRevHash);
};

exports.createCanopyBoundariesTileLayer = function () {
    var url = exports.getCanopyBoundariesTileLayerUrl(),
        options = _.extend({}, MAX_ZOOM_OPTION, CANOPY_BOUNDARY_LAYER_OPTION);
    return L.tileLayer(url, options);
};

exports.createPlotTileLayer = function () {
    var options = _.extend({}, MAX_ZOOM_OPTION, FEATURE_LAYER_OPTION);
    return filterableLayer(
        'treemap_mapfeature', 'png', options);
};

exports.createPolygonTileLayer = function () {
    var options = _.extend({}, MAX_ZOOM_OPTION, MIN_ZOOM_OPTION, FEATURE_LAYER_OPTION);
    return filterableLayer(
        'stormwater_polygonalmapfeature', 'png', options);
};

exports.createPlotUTFLayer = function () {
    var layer,
        revToUrl = getUrlMaker('treemap_mapfeature', 'grid.json'),
        url = revToUrl(config.instance.geoRevHash),
        options = _.extend({resolution: 4}, MAX_ZOOM_OPTION, FEATURE_LAYER_OPTION);

    // Need to use JSONP on on browsers that do not support CORS (IE9)
    // Only applies to plot layer because only UtfGrid is using XmlHttpRequest
    // for cross-site requests
    if (!$.support.cors) {
        url += '&callback={cb}';
        options.useJsonP = true;
    } else {
        options.useJsonP = false;
    }

    layer = new L.utfGrid(url, options);

    layer.setHashes = function (hashes) {
        layer.setUrl(revToUrl(hashes.geoRevHash));
    };

    layer.setUrl = function(url) {
        // Poke some internals
        // Update the url
        layer._url = url;
        // bust the cache
        layer._cache = {};

        // Trigger update
        layer._update();
    };

    return layer;
};

exports.createCustomLayer = function(layerInfo) {
    if (layerInfo.type === 'tile') {
        var options = _.extend({}, CUSTOM_LAYER_OPTION);
        options.maxZoom = layerInfo.maxZoom || MAX_ZOOM_OPTION.maxZoom;
        if (layerInfo.maxNativeZoom) {
            options.maxNativeZoom = layerInfo.maxNativeZoom;
        }
        if (layerInfo.opacity) {
            options.opacity = layerInfo.opacity;
        }
        return L.tileLayer(layerInfo.url, options);
    }
};

////////////////////////////////////////////////
// internal functions
////////////////////////////////////////////////

function getUrlMaker(table, extension, tilerArgs) {
    return function revToUrl(rev) {
        var query = {
            'instance_id': config.instance.id,
            'restrict': JSON.stringify(config.instance.mapFeatureTypes)
        };

        if (tilerArgs) {
            _.extend(query, tilerArgs);
        }

        return format(
            '%s/tile/%s/database/otm/table/%s/{z}/{x}/{y}.%s%s',
            config.tileHost || '', rev, table, extension,
            urlLib.format({query: query}));
    };
}

// Combine base from `newBaseUrl` with querystring from `url`.
//
// The purpose of this is to generate a new search url for tile layers
// from an updated base url (because of revision hash changes), while
// also preserving the current querystring filters.
//
// Ref: https://github.com/OpenTreeMap/otm-core/issues/2437
function updateBaseUrl(url, newBaseUrl) {
    var oldQueryString = url.split('?')[1],
        newBase = newBaseUrl.split('?')[0];
    return newBase + '?' + oldQueryString;
}

function filterableLayer (table, extension, layerOptions) {
    var revToUrl = getUrlMaker(table, extension),
        noSearchUrl = revToUrl(config.instance.geoRevHash),
        searchBaseUrl = revToUrl(config.instance.universalRevHash),
        layer = L.tileLayer(noSearchUrl, layerOptions);

    layer.setHashes = function(response) {
        noSearchUrl = revToUrl(response.geoRevHash);
        searchBaseUrl = revToUrl(response.universalRevHash);

        // Update tiles to reflect content changes.
        var newLayerUrl = updateBaseUrl(layer._url, searchBaseUrl);
        layer.setUrl(newLayerUrl);
    };

    layer.setFilter = function(filters) {
        var fullUrl;
        if (Search.isEmpty(filters)) {
            fullUrl = noSearchUrl;
        } else {
            var query = Search.makeQueryStringFromFilters(filters);
            var suffix = query ? '&' + query : '';
            fullUrl = searchBaseUrl + suffix;
        }
        layer.setUrl(fullUrl);
    };

    return layer;
}
