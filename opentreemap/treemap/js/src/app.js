"use strict";

var $ = require('jquery'),
    OL = require('OpenLayers'),
    Bacon = require('baconjs'),
    U = require('./utility'),

    Search = require('./search'),
    otmTypeahead = require('./otmTypeahead'),
    makeLayerFilterable = require('./makeLayerFilterable'),
    modes = require('./modeManagerForMapPage'),

    isEnterKey = require('./baconUtils').isEnterKey;

// This module augments the OpenLayers global so we don't need `var thing =`
require('./openLayersMapEventStream');
require('./csrf');  // set up cross-site forgery protection for $.ajax()


var app = {
    createMap: function (elmt, config) {
        var map = new OL.Map({
            theme: null,
            div: elmt,
            projection: 'EPSG:3857',
            layers: this.getBasemapLayers(config)
        });

        return map;
    },

    getBasemapLayers: function (config) {
        var layer;
        if (config.instance.basemap.type === 'bing') {
            layer = new OL.Layer.Bing({
                name: 'Road',
                key: config.instance.basemap.bing_api_key,
                type: 'Road',
                isBaseLayer: true
            });
        } else if (config.instance.basemap.type === 'tms') {
            layer = new OL.Layer.XYZ(
                'xyz',
                config.instance.basemap.data);
        } else {
            layer = new OL.Layer.Google(
                "Google Streets",
                {numZoomLevels: 20});
        }
        return [layer];
    },

    getPlotLayerURL: function(config, extension) {
        return '/tile/' +
            config.instance.rev +
            '/database/otm/table/treemap_plot/${z}/${x}/${y}.' +
            extension + '?instance_id=' + config.instance.id;
    },

    createPlotTileLayer: function (config) {
        var url = this.getPlotLayerURL(config, 'png'),
            layer = new OL.Layer.XYZ(
                'tiles',
                url,
                { isBaseLayer: false,
                  sphericalMercator: true });
        makeLayerFilterable(layer, url, config.urls.filterQueryArgumentName);
        return layer;
    },

    createPlotUTFLayer: function (config) {
        var url = this.getPlotLayerURL(config, 'grid.json'),
            layer = new OL.Layer.UTFGrid({
                url: url,
                utfgridResolution: 4
            });
        makeLayerFilterable(layer, url, config.urls.filterQueryArgumentName);
        return layer;
    },

    getBoundsLayerURL: function(config, extension) {
        return '/tile/' +
            config.instance.rev +
            '/database/otm/table/treemap_boundary/${z}/${x}/${y}.' +
            extension + '?instance_id=' + config.instance.id;
    },

    createBoundsTileLayer: function (config) {
        return new OL.Layer.XYZ(
            'bounds',
            this.getBoundsLayerURL(config, 'png'),
            { isBaseLayer: false,
              sphericalMercator: true });
    },

    initTypeAheads: function(config) {
        otmTypeahead.create({
            name: "species",
            url: "/" + config.instance.id + "/species",
            input: "#species-typeahead",
            template: "#species-element-template",
            hidden: "#search-species",
            reverse: "id"
        });
        otmTypeahead.create({
            name: "boundaries",
            url: "/" + config.instance.id + "/boundaries",
            input: "#boundary-typeahead",
            template: "#boundary-element-template",
            hidden: "#boundary",
            reverse: "id"
        });
    },

    resetEventStream: function() {
        return $("#search-reset").asEventStream("click");
    },

    searchEventStream: function() {
        var enterKeyPressStream = $('input[data-class="search"]')
                .asEventStream("keyup")
                .filter(isEnterKey),

            performSearchClickStream = $("#perform-search")
                .asEventStream("click"),

            triggerEventStream = enterKeyPressStream.merge(
                performSearchClickStream);

        return triggerEventStream;
    },

    redirectToSearchPage: function (config, query) {
        query = U.getUpdatedQueryString('q', JSON.stringify(query));

        window.location.href =
            '/' + config.instance.id + '/map/?' + query;
    }
};

module.exports = {
    init: function (config) {
        app.resetEventStream()
            .map({})
            .onValue(Search.applySearchToDom);

        app.initTypeAheads(config);

        app.searchEventStream()
            .map(Search.buildSearch)
            .onValue(app.redirectToSearchPage, config);
    },

    initMapPage: function (config) {
        var map = app.createMap($("#map")[0], config),
            plotLayer = app.createPlotTileLayer(config),
            boundsLayer = app.createBoundsTileLayer(config),
            utfLayer = app.createPlotUTFLayer(config),
            zoom = 0,
            searchEventStream = app.searchEventStream(),
            resetStream = app.resetEventStream();

        app.initTypeAheads(config);

        // Bing maps uses a 1-based zoom so XYZ layers
        // on the base map have a zoom offset that is
        // always one less than the map zoom:
        // > map.setCenter(center, 11)
        // > map.zoom
        //   12
        // So this forces the tile requests to use
        // the correct Z offset
        if (config.instance.basemap.type === 'bing') {
            plotLayer.zoomOffset = 1;
            utfLayer.zoomOffset = 1;
        }

        map.addLayer(plotLayer);
        map.addLayer(utfLayer);
        map.addLayer(boundsLayer);

        var clickedLatLonStream = map.asEventStream('click').map(function (e) {
            return map.getLonLatFromPixel(e.xy);
        });

        zoom = map.getZoomForResolution(76.43702827453613);
        map.setCenter(config.instance.center, zoom);

        modes.init(config, map, clickedLatLonStream);
        modes.activateBrowseTreesMode();

        // Use a bus to delay sending the initial signal
        // seems like you could merge with Bacon.once(initialSearch)
        // but that empirically doesn't work

        // Don't duplicate queries
        var lastQuery = null;

        var triggerSearchFromUrl = new Bacon.Bus();
        var initialQueryBus = triggerSearchFromUrl.flatMap(function() {
            var query = U.parseQueryString().q || '{}';
            if (lastQuery != query) {
                lastQuery = query;
                return JSON.parse(query);
            } else {
                return Bacon.never();
            }
        });
        var triggeredQueryBus = resetStream.map({})
                                           .merge(initialQueryBus);

        window.addEventListener('popstate', function(event) {
            triggerSearchFromUrl.push({});
        }, false);

        var builtSearchEvents = searchEventStream
                .merge(resetStream)
                .map(Search.buildSearch)
                .merge(triggeredQueryBus);

        triggeredQueryBus.onValue(Search.applySearchToDom);

        Search.init(builtSearchEvents, config, function (filter) {
            plotLayer.setFilter(filter);
            utfLayer.setFilter(filter);
        });

        builtSearchEvents
            .map(JSON.stringify)
            .map(function(q) {
                if (q == '{}') {
                    return null;
                } else {
                    return q;
                }
            })
            .map(U.getUpdateUrlByUpdatingQueryStringParam, 'q')
            .filter(function(url) {
                return url != window.location.href;
            })
            .onValue(U.pushState);

        triggerSearchFromUrl.push({});

    }
};
