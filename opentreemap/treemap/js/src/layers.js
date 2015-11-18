"use strict";

var $ = require("jquery"),
    _ = require("lodash"),
    L = require('leaflet'),
    urlLib = require('url'),
    Search = require("treemap/search"),
    format = require('util').format,

    MAX_ZOOM_OPTION = exports.MAX_ZOOM_OPTION = {maxZoom: 21},
    // Min zoom level for detail layers
    MIN_ZOOM_OPTION = exports.MIN_ZOOM_OPTION = {minZoom: 15};

////////////////////////////////////////////////
// public functions
////////////////////////////////////////////////

exports.createBoundariesTileLayer = function (config) {
    // we will never update boundaries based on a revision, so
    // safe to use the same url permanently.
    var revToUrl = getUrlMaker(config, 'treemap_boundary', 'png'),
        url = revToUrl(config.instance.geoRevHash),
        options = _.extend({}, MAX_ZOOM_OPTION, MIN_ZOOM_OPTION);
    return L.tileLayer(url, options);
};

exports.createPlotTileLayer = function (config) {
    return filterableLayer(
        'treemap_mapfeature', 'png', config, MAX_ZOOM_OPTION);
};

exports.createPolygonTileLayer = function (config) {
    var options = _.extend({}, MAX_ZOOM_OPTION, MIN_ZOOM_OPTION);
    return filterableLayer(
        'stormwater_polygonalmapfeature', 'png', config, options);
};

exports.createPlotUTFLayer = function (config) {
    var layer,
        revToUrl = getUrlMaker(
            config, 'treemap_mapfeature', 'grid.json'),
        url = revToUrl(config.instance.geoRevHash),
        options = _.extend({resolution: 4}, MAX_ZOOM_OPTION);

    // Need to use JSONP on on browsers that do not support CORS (IE9)
    // Only applies to plot layer because only UtfGrid is using XmlHttpRequest
    // for cross-site requests
    if (!$.support.cors) {
        url += '&callback={cb}';
        options.useJsonP = true;
    } else {
        options.useJsonP = false;
    }

    layer = new L.UtfGrid(url, options);

    layer.setHashes = function (hashes) {
        layer.setUrl(revToUrl(hashes.geoRevHash));
    };

    // TODO: I don't think this is used anywhere. can we delete it?
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

////////////////////////////////////////////////
// internal functions
////////////////////////////////////////////////

function getUrlMaker(config, table, extension) {
    return function revToUrl(rev) {
        return format(
            '%s/tile/%s/table/%s/{z}/{x}/{y}.%s%s',
            config.tileHost || '', rev, table, extension,
            urlLib.format({query: {
                'instance_id': config.instance.id,
                'restrict': JSON.stringify(config.instance.mapFeatureTypes)
            }}));
    };
}

function filterableLayer (table, extension, config, layerOptions) {
    var revToUrl = getUrlMaker(config, table, extension),
        noSearchUrl = revToUrl(config.instance.geoRevHash),
        searchBaseUrl = revToUrl(config.instance.universalRevHash),
        layer = L.tileLayer(noSearchUrl, layerOptions);

    layer.setHashes = function(response) {
        noSearchUrl = revToUrl(response.geoRevHash);
        searchBaseUrl = revToUrl(response.universalRevHash);

        // TODO: this is cryptic. This method gets called even when a
        // search is activated, so setting the URL to the noSearchUrl
        // would seem to clear the search, only it doesn't. I guess
        // setFilter is being called again, afterward, somewhere else.
        // unfortunately, this is necessary because without it new
        // tiles don't get requested, and we haven't closed over filters
        // so we can't simply make another call to `setFilter`.
        layer.setUrl(noSearchUrl);
    };

    layer.setFilter = function(filters) {
        var fullUrl;
        if (Search.isEmpty(filters)) {
            fullUrl = noSearchUrl;
        } else {
            var query = Search.makeQueryStringFromFilters(config, filters);
            var suffix = query ? '&' + query : '';
            fullUrl = searchBaseUrl + suffix;
        }
        layer.setUrl(fullUrl);
    };

    return layer;
}
