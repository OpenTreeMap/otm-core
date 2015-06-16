"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    U = require('treemap/utility'),
    BU = require('treemap/baconUtils'),
    makeLayerFilterable = require('treemap/makeLayerFilterable'),
    urlState = require('treemap/urlState'),

    MAX_ZOOM_OPTION = {maxZoom: 21},
    // Min zoom level for detail layers
    MIN_ZOOM_OPTION = {minZoom: 15};

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
            hasPolygons = getDomMapBool('has-polygons', options.domId),
            hasBoundaries = getDomMapBool('has-boundaries', options.domId),
            plotLayer = createPlotTileLayer(config),
            allPlotsLayer = createPlotTileLayer(config),
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

            if (hasPolygons) {
                var polygonLayer = createPolygonTileLayer(config),
                    allPolygonsLayer = createPolygonTileLayer(config);
                this._hasPolygons = hasPolygons;
                this._polygonLayer = polygonLayer;
                this._allPolygonsLayer = allPolygonsLayer;
                allPolygonsLayer.setOpacity(0.3);
                map.addLayer(polygonLayer);
            }
        }

        if (hasBoundaries) {
            var boundariesLayer = createBoundariesTileLayer(config);
            map.addLayer(boundariesLayer);
            this.layersControl.addOverlay(boundariesLayer, 'Boundaries');
        }

        if (options.trackZoomLatLng) {
            map.on("moveend", _.partial(serializeZoomLatLngFromMap, map));
            urlState.stateChangeStream.filter('.zoomLatLng')
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

            if (this._hasPolygons) {
                pngUrl = getPolygonLayerURL(this._config, 'png');
                this._polygonLayer.setUnfilteredUrl(pngUrl);
                this._allPolygonsLayer.setUnfilteredUrl(pngUrl);
            }
        }
    },

    setFilter: function (filter) {
        this._plotLayer.setFilter(filter);

        if (!this._allPlotsLayer.map) {
            this.map.addLayer(this._allPlotsLayer);
            if (this._hasPolygons) {
                this.map.addLayer(this._allPolygonsLayer);
            }
        }
        if (_.isEmpty(filter)) {
            this.map.removeLayer(this._allPlotsLayer);
            if (this._hasPolygons) {
                this.map.removeLayer(this._allPolygonsLayer);
            }
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
        layers = [L.tileLayer(config.instance.basemap.data, MAX_ZOOM_OPTION)];
    } else {
        return {'Streets': new L.Google('ROADMAP', MAX_ZOOM_OPTION),
                'Hybrid': new L.Google('HYBRID', MAX_ZOOM_OPTION),
                'Satellite': new L.Google('SATELLITE', MAX_ZOOM_OPTION)};
    }
    return layers;
}

function createPlotTileLayer(config) {
    var url = getPlotLayerURL(config, 'png'),
        layer = L.tileLayer(url, MAX_ZOOM_OPTION);
    makeLayerFilterable(layer, url, config);
    return layer;
}

function createPolygonTileLayer(config) {
    var url = getPolygonLayerURL(config, 'png'),
        options = _.extend({}, MAX_ZOOM_OPTION, MIN_ZOOM_OPTION),
        layer = L.tileLayer(url, options);
    makeLayerFilterable(layer, url, config);
    return layer;
}

function createPlotUTFLayer(config) {
    var layer, url = getPlotLayerURL(config, 'grid.json'),
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

function createBoundariesTileLayer(config) {
    var url = getLayerURL(config, 'treemap_boundary', 'png'),
        options = _.extend({}, MAX_ZOOM_OPTION, MIN_ZOOM_OPTION);
    return L.tileLayer(url, options);
}

function getPlotLayerURL(config, extension) {
    return getLayerURL(config, 'treemap_mapfeature', extension);
}

function getPolygonLayerURL(config, extension) {
    return getLayerURL(config, 'stormwater_polygonalmapfeature', extension);
}

function getLayerURL(config, layer, extension) {
    var host = config.tileHost || '';
    return host + '/tile/' +
        config.instance.rev +
        '/database/otm/table/' + layer + '/{z}/{x}/{y}.' +
        extension + '?instance_id=' + config.instance.id;
}

function deserializeZoomLatLngAndSetOnMap(mapManager, state) {
    var zll = state.zoomLatLng,
        center = new L.LatLng(zll.lat, zll.lng);
    mapManager.setCenterAndZoomLL(zll.zoom, center);
}

function serializeZoomLatLngFromMap(map) {
    var zoom = map.getZoom(),
        center = map.getCenter();
    urlState.setZoomLatLng(zoom, center);
}

function getDomMapBool(dataAttName, domId) {
    return (getDomMapAttribute(dataAttName, domId) == 'True');
}

function getDomMapAttribute(dataAttName, domId) {
    domId = domId || 'map';
    var $map = $('#' + domId),
        value = $map.data(dataAttName);
    return value;
}

module.exports = MapManager;
