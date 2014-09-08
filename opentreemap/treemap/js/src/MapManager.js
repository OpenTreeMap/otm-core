"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    U = require('treemap/utility'),
    BU = require('treemap/baconUtils'),
    makeLayerFilterable = require('treemap/makeLayerFilterable'),
    mapState = require('treemap/mapState');

// Leaflet extensions
require('utfgrid');
require('leafletbing');
require('leafletgoogle');

var MapManager = function() {};  // constructor

MapManager.prototype = {
    ZOOM_DEFAULT: 11,
    ZOOM_PLOT: 18,

    createTreeMap: function (options) {
        var config = options.config,
            plotLayer = createPlotTileLayer(config),
            allPlotsLayer = createPlotTileLayer(config),
            boundsLayer = createBoundsTileLayer(config),
            utfLayer = createPlotUTFLayer(config);

        this._config = config;
        this._plotLayer = plotLayer;
        this._allPlotsLayer = allPlotsLayer;
        this._utfLayer = utfLayer;

        allPlotsLayer.setOpacity(0.3);

        options.centerWM = options.centerWM || config.instance.center;
        options.zoom = options.zoom || this.ZOOM_DEFAULT;
        var map = this.createMap(options);

        if (options.plotLayerViewOnly) {
            this.layersControl.addOverlay(plotLayer, 'OpenTreeMap Trees');
        } else {
            map.addLayer(plotLayer);
            map.addLayer(utfLayer);
            map.utfEvents = BU.leafletEventStream(utfLayer, 'click');
        }

        map.addLayer(boundsLayer);
        this.layersControl.addOverlay(boundsLayer, 'Boundaries');

        if (options.trackZoomLatLng) {
            map.on("moveend", _.partial(serializeZoomLatLngFromMap, map));
            mapState.stateChangeStream.filter('.zoomLatLng')
                .onValue(_.partial(deserializeZoomLatLngAndSetOnMap, this));
        }

        return map;
    },

    createMap: function (options) {
        var center = options.centerWM || {x: 0, y: 0},
            zoom = options.zoom || 2,
            map = L.map(options.domId, {
                center: U.webMercatorToLeafletLatLng(center.x, center.y),
                zoom: zoom
            }),
            basemapMapping = getBasemapLayers(options.config);

        if (_.isArray(basemapMapping)) {
            _.each(_.values(basemapMapping),
                function (layer) {
                    map.addLayer(layer);
                });
        } else {
            var visible = _.keys(basemapMapping)[0];
            map.addLayer(basemapMapping[visible]);
            this.layersControl = L.control.layers(basemapMapping).addTo(map);
        }

        if (options.disableScrollWithMouseWheel) {
            map.scrollWheelZoom = false;
        }

        this.map = map;
        return map;
    },

    updateGeoRevHash: function (geoRevHash) {
        if (geoRevHash !== this._config.instance.rev) {
            this._config.instance.rev = geoRevHash;

            var pngUrl = getPlotLayerURL(this._config, 'png');
            this._plotLayer.setUnfilteredUrl(pngUrl);
            this._allPlotsLayer.setUnfilteredUrl(pngUrl);

            this._utfLayer.setUrl(getPlotLayerURL(this._config, 'grid.json'));
        }
    },

    setFilter: function (filter) {
        this._plotLayer.setFilter(filter);

        if (!this._allPlotsLayer.map) {
            this.map.addLayer(this._allPlotsLayer);
        }
        if (_.isEmpty(filter)) {
            this.map.removeLayer(this._allPlotsLayer);
        }
    },

    setCenterAndZoomLL: function (zoom, location, reset) {
        // Never zoom out, or try to zoom farther than allowed.
        var zoomToApply = Math.max(
            this.map.getZoom(),
            Math.min(zoom, this.map.getMaxZoom()));

        this.map.setView(location, zoomToApply, {reset: !!reset});
    },

    setCenterAndZoomWM: function (zoom, location, reset) {
        this.setCenterAndZoomLL(
            zoom,
            U.webMercatorToLeafletLatLng(location.x, location.y),
            reset);
    },

    setCenterWM: function(location, reset) {
        this.setCenterAndZoomWM(this.ZOOM_PLOT, location, reset);
    },

    setCenterLL: function(location, reset) {
        this.setCenterAndZoomLL(this.ZOOM_PLOT, location, reset);
    }
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
    makeLayerFilterable(layer, url, config);
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
    return getLayerURL(config, 'treemap_mapfeature', extension);
}

function getBoundsLayerURL(config, extension) {
    return getLayerURL(config, 'treemap_boundary', extension);
}

function createBoundsTileLayer(config) {
    return L.tileLayer(
        getBoundsLayerURL(config, 'png'),
        { maxZoom: 20 });
}

function deserializeZoomLatLngAndSetOnMap(mapManager, state) {
    var zll = state.zoomLatLng,
        center = new L.LatLng(zll.lat, zll.lng);
    mapManager.setCenterAndZoomLL(zll.zoom, center);
}

function serializeZoomLatLngFromMap(map) {
    var zoom = map.getZoom(),
        center = map.getCenter();
    mapState.setZoomLatLng(zoom, center);
}

module.exports = MapManager;
