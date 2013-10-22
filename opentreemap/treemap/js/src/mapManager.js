"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    google = require('googlemaps'),
    L = require('leaflet'),
    U = require('utility'),
    Bacon = require('baconjs'),
    BU = require('BaconUtils'),
    makeLayerFilterable = require('./makeLayerFilterable');

// Leaflet extensions
require('utfgrid');
require('leafletbing');
require('leafletgoogle');

exports.ZOOM_DEFAULT = 11;
exports.ZOOM_PLOT = 18;


exports.init = function(options) {
    var config = options.config,
        mapOptions = {
            disableScrollWithMouseWheel: options.disableScrollWithMouseWheel
        },
        map = createMap($(options.selector)[0], config, mapOptions),
        plotLayer = createPlotTileLayer(config),
        allPlotsLayer = createPlotTileLayer(config),
        boundsLayer = createBoundsTileLayer(config),
        utfLayer = createPlotUTFLayer(config);

    allPlotsLayer.setOpacity(0.3);

    exports.map = map;

    map.utfEvents = BU.leafletEventStream(utfLayer, 'click');

    exports.updateGeoRevHash = function(geoRevHash) {
        if (geoRevHash !== config.instance.rev) {
            config.instance.rev = geoRevHash;

            var pngUrl = getPlotLayerURL(config, 'png');
            plotLayer.setUnfilteredUrl(pngUrl);
            allPlotsLayer.setUnfilteredUrl(pngUrl);

            utfLayer.setUrl(getPlotLayerURL(config, 'grid.json'));
        }
    };

    exports.setFilter = function (filter) {
        plotLayer.setFilter(filter);

        if (!allPlotsLayer.map) {
            map.addLayer(allPlotsLayer);
        }
        if (_.isEmpty(filter)) {
            map.removeLayer(allPlotsLayer);
        }
    };

    var setCenterAndZoomIn = exports.setCenterAndZoomIn = function(location, zoom, reset) {
        if (zoom > map.getMaxZoom()) {
            zoom = map.getMaxZoom();
        }

        var ll = U.webMercatorToLatLng(location.x, location.y);
        map.setView(new L.LatLng(ll.lat, ll.lng),
                    Math.max(map.getZoom(), zoom),
                    {reset: !!reset});
    };

    map.addLayer(boundsLayer);
    map.addLayer(utfLayer);
    map.addLayer(plotLayer);

    var center = options.center || config.instance.center,
        zoom = options.zoom || exports.ZOOM_DEFAULT;
    setCenterAndZoomIn(center, zoom);
};

var createMap = exports.createMap = function(elmt, config, options) {
    options = options || {};

    var basemapMapping = getBasemapLayers(config);

    var map = L.map(elmt, {center: new L.LatLng(0.0, 0.0), zoom: 2});

    if (_.isArray(basemapMapping)) {
        _.each(_.values(basemapMapping),
               function(layer) { map.addLayer(layer); });
    } else {
        var visible = _.keys(basemapMapping)[0];

        map.addLayer(basemapMapping[visible]);

        L.control.layers(basemapMapping).addTo(map);
    }

    if (options.disableScrollWithMouseWheel) {
        map.scrollWheelZoom = false;
    }

    return map;
};

function getBasemapLayers(config) {
    function makeBingLayer(layer) {
        return new L.BingLayer(
            config.instance.basemap.bing_api_key,
            {type: layer});
    }

    var layers;
    if (config.instance.basemap.type === 'bing') {
        return {
            'Road': makeBingLayer('Road'),
            'Aerial': makeBingLayer('Aerial'),
            'Hybrid': makeBingLayer('AerialWithLabels')
        };
    } else if (config.instance.basemap.type === 'tms') {
        layers = [L.tileLayer(config.instance.basemap.data, { maxZoom: 20 })];
    } else {
        return {'Streets': new L.Google('ROADMAP', { maxZoom: 20 }),
                'Hybrid': new L.Google('HYBRID', { maxZoom: 20 }),
                'Satellite': new L.Google('SATELLITE', { maxZoom: 20 })};
    }
    return layers;
}

function createPlotTileLayer(config) {
    var url = getPlotLayerURL(config, 'png'),
        layer = L.tileLayer(url, { maxZoom: 20 });
    makeLayerFilterable(layer, url, config.urls.filterQueryArgumentName);
    return layer;
}

function createPlotUTFLayer(config) {
    var layer, url = getPlotLayerURL(config, 'grid.json'),
        options = {
            resolution: 4,
            maxZoom: 20
        };
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
}

// Leaflet uses {s} to indicate subdomains
function getLayerURL(config, layer, extension) {
    var host = config.tileHost || '';
    return host + '/tile/' +
        config.instance.rev +
        '/database/otm/table/' + layer + '/{z}/{x}/{y}.' +
        extension + '?instance_id=' + config.instance.id;
}

function getPlotLayerURL(config, extension) {
    return getLayerURL(config, 'treemap_plot', extension);
}

function getBoundsLayerURL(config, extension) {
    return getLayerURL(config, 'treemap_boundary', extension);
}

function createBoundsTileLayer(config) {
    return L.tileLayer(
        getBoundsLayerURL(config, 'png'),
        { maxZoom: 20 });
}
