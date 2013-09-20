"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    OL = require('OpenLayers'),
    makeLayerFilterable = require('./makeLayerFilterable');

exports.ZOOM_DEFAULT = 11;
exports.ZOOM_PLOT = 18;

exports.init = function(options) {
    var config = options.config,
        map = createMap($(options.selector)[0], config),
        plotLayer = createPlotTileLayer(config),
        allPlotsLayer = createPlotTileLayer(config),
        boundsLayer = createBoundsTileLayer(config),
        utfLayer = createPlotUTFLayer(config);

    allPlotsLayer.setOpacity(0.3);

    exports.map = map;

    exports.updateGeoRevHash = function(geoRevHash) {
        if (geoRevHash !== config.instance.rev) {
            config.instance.rev = geoRevHash;
            plotLayer.url = getPlotLayerURL(config, 'png');
            allPlotsLayer.url = getPlotLayerURL(config, 'png');
            utfLayer.url = getPlotLayerURL(config, 'grid.json');
            plotLayer.redraw({force: true});
            utfLayer.redraw({force: true});
        }
    };

    exports.setFilter = function (filter) {
        plotLayer.setFilter(filter);

        if (!allPlotsLayer.map) {
            map.addLayers([allPlotsLayer]);
        }
        if (_.isEmpty(filter)) {
            map.removeLayer(allPlotsLayer);
        }

    };

    var setCenterAndZoomIn = exports.setCenterAndZoomIn = function(location, zoom) {
        // I could not find a documented way of getting the max
        // zoom level allowed by the current base layer so
        // I am using isValidZoomLevel to find it.
        while (zoom > 1 && !map.isValidZoomLevel(zoom)) {
            zoom -= 1;
        }
        map.setCenter(new OL.LonLat(location.x, location.y),
                      Math.max(map.getZoom(), zoom));
    };

    // Bing maps uses a 1-based zoom so XYZ layers on the base map have
    // a zoom offset that is always one less than the map zoom:
    // > map.setCenter(center, 11)
    // > map.zoom
    //   12
    // So this forces the tile requests to use the correct Z offset
    if (config.instance.basemap.type === 'bing') {
        plotLayer.zoomOffset = 1;
        utfLayer.zoomOffset = 1;
    }

    map.addLayer(plotLayer);
    map.addLayer(utfLayer);
    map.addLayer(boundsLayer);

    var center = options.center || config.instance.center,
        zoom = options.zoom || exports.ZOOM_DEFAULT;
    setCenterAndZoomIn(center, zoom);
};

function createMap(elmt, config) {
    OL.ImgPath = "/static/img/";

    var map = new OL.Map({
        theme: null,
        div: elmt,
        projection: 'EPSG:3857',
        layers: getBasemapLayers(config)
    });

    var switcher = new OL.Control.LayerSwitcher();
    map.addControls([switcher]);

    return map;
}

function getBasemapLayers(config) {
    var layers;
    if (config.instance.basemap.type === 'bing') {
        layers = [
            new OL.Layer.Bing({
                name: 'Road',
                key: config.instance.basemap.bing_api_key,
                type: 'Road',
                isBaseLayer: true
            }),
            new OL.Layer.Bing({
                name: 'Aerial',
                key: config.instance.basemap.bing_api_key,
                type: 'Aerial',
                isBaseLayer: true
            }),
            new OL.Layer.Bing({
                name: 'Hybrid',
                key: config.instance.basemap.bing_api_key,
                type: 'AerialWithLabels',
                isBaseLayer: true
            })];
    } else if (config.instance.basemap.type === 'tms') {
        layers = [new OL.Layer.XYZ(
            'xyz',
            config.instance.basemap.data)];
    } else {
        layers = [
            new OL.Layer.Google(
                "Google Streets",
                {numZoomLevels: 20}),
            new OL.Layer.Google(
                "Google Hybrid",
                {type: google.maps.MapTypeId.HYBRID,
                 numZoomLevels: 20}),
            new OL.Layer.Google(
                "Google Satellite",
                {type: google.maps.MapTypeId.SATELLITE, numZoomLevels: 22})];
    }
    return layers;
}

function createPlotTileLayer(config) {
    var url = getPlotLayerURL(config, 'png'),
        layer = new OL.Layer.XYZ(
            'tiles',
            url,
            { isBaseLayer: false,
              sphericalMercator: true,
              displayInLayerSwitcher: false });
    makeLayerFilterable(layer, url, config.urls.filterQueryArgumentName);
    return layer;
}

function createPlotUTFLayer(config) {
    var url = getPlotLayerURL(config, 'grid.json'),
        layer = new OL.Layer.UTFGrid({
            url: url,
            utfgridResolution: 4,
            displayInLayerSwitcher: false
        });
    return layer;
}

// The ``url`` property of the OpenLayers XYZ layer supports a single
// string or an array of strings. ``getPlotLayerURL`` looks at
// ``config.tileHosts`` and returns a single string if only one host
// is defined, or an array of strings if multiple hosts are defined.
function getPlotLayerURL(config, extension) {
    var urls = [],
        // Using an array with a single undefined element when
        // ``config.tileHosts`` is falsy allows us to always
        // use an ``_.each`` loop to generate the url string,
        // simplifying the code path
        hosts = config.tileHosts || [undefined];
    _.each(hosts, function(host) {
        var prefix = host ? '//' + host : '';
        urls.push(prefix + '/tile/' +
        config.instance.rev +
        '/database/otm/table/treemap_plot/${z}/${x}/${y}.' +
        extension + '?instance_id=' + config.instance.id);
    });
    return urls.length === 1 ? urls[0] : urls;
}

function createBoundsTileLayer(config) {
    return new OL.Layer.XYZ(
        'bounds',
        getBoundsLayerURL(config, 'png'),
        { isBaseLayer: false,
          sphericalMercator: true,
          displayInLayerSwitcher: false });
}

function getBoundsLayerURL(config, extension) {
    return '/tile/' +
        config.instance.rev +
        '/database/otm/table/treemap_boundary/${z}/${x}/${y}.' +
        extension + '?instance_id=' + config.instance.id;
}
