"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    OL = require('OpenLayers'),
    Bacon = require('baconjs'),

    Search = require('./search'),
    otmTypeahead = require('./otmTypeahead'),
    makeLayerFilterable = require('./makeLayerFilterable'),

    isEnterKey = require('./baconUtils').isEnterKey,
    truthyOrError = require('./baconUtils').truthyOrError;

// These modules add features to the OpenLayers global
// so we do not need `var thing =`
require('./openLayersUtfGridEventStream');
require('./openLayersMapEventStream');

function parseQueryString() {
    var match,
        pl     = /\+/g,  // Regex for replacing addition symbol with a space
        search = /([^&=]+)=?([^&]*)/g,
        decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
        query  = window.location.search.substring(1),
        urlParams = {};

    while ((match = search.exec(query))) {
        urlParams[decode(match[1])] = decode(match[2]);
    }

    return urlParams;
}

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

    getPlotPopupContent: function(config, id) {
        var search = $.ajax({
            url: '/' + config.instance.id + '/plots/' + id + '/popup',
            type: 'GET',
            dataType: 'html'
        });
        return Bacon.fromPromise(search);
    },

    makePopup: function(latLon, html, size) {
        if (latLon && html) {
            return new OL.Popup("plot-popup", latLon, size, html, true);
        } else {
            return null;
        }
    },

    getPlotAccordianContent: function(config, id) {
        var search = $.ajax({
            url: '/' + config.instance.id + '/plots/' + id + '/detail',
            type: 'GET',
            dataType: 'html'
        });
        return Bacon.fromPromise(search);
    },

    initTypeAheads: function(config) {
        otmTypeahead.create({
            name: "species",
            url: "/" + config.instance.id + "/species",
            input: "#species-typeahead",
            template: "#species-element-template",
            hidden: "#search-species"
        });
        otmTypeahead.create({
            name: "boundaries",
            url: "/" + config.instance.id + "/boundaries",
            input: "#boundary-typeahead",
            template: "#boundary-element-template",
            hidden: "#boundary"
        });
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
        query = JSON.stringify(query);

        window.location.href =
            '/' + config.instance.id + '/map/?q=' + query;
    }
};

function showPlotAccordian(html) {
    $('#plot-accordian').html(html);
    $("#treeDetails").removeClass('collapse');
}

module.exports = {
    init: function (config) {
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
            searchEventStream = app.searchEventStream();

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

        var utfGridMoveControl = new OL.Control.UTFGrid();

        utfGridMoveControl
            .asEventStream('move')
            .map(function (o) { return JSON.stringify(o || {}); })
            .assign($('#attrs'), 'html');

        // The control must be added to the map after setting up the
        // event stream
        map.addControl(utfGridMoveControl);

        var utfGridClickControl = new OL.Control.UTFGrid();

        var clickedIdStream = utfGridClickControl
            .asEventStream('click')
            .map('.' + config.utfGrid.plotIdKey)
            .map(truthyOrError); // Prevents making requests if id is undefined

        var popupHtmlStream = clickedIdStream
            .flatMap(_.bind(app.getPlotPopupContent, app, config))
            .mapError(''); // No id or a server error both result in no content

        var accordianHtmlStream = clickedIdStream
            .flatMap(_.bind(app.getPlotAccordianContent, app, config))
            .mapError('')
            .onValue(showPlotAccordian);

        // The control must be added to the map after setting up the
        // event streams
        map.addControl(utfGridClickControl);

        var showPlotDetailPopup = (function(map) {
            var existingPopup;
            return function(popup) {
                if (existingPopup) { map.removePopup(existingPopup); }
                if (popup) { map.addPopup(popup); }
                existingPopup = popup;
            };
        }(map));

        var clickedLatLonStream = map.asEventStream('click').map(function (e) {
            return map.getLonLatFromPixel(e.xy);
        });

        // OpenLayers needs both the content and a coordinate to
        // show a popup so I zip map clicks together with content
        // requested via ajax
        clickedLatLonStream
            .zip(popupHtmlStream, app.makePopup) // TODO: size is not being sent to makePopup
            .onValue(showPlotDetailPopup);

        zoom = map.getZoomForResolution(76.43702827453613);
        map.setCenter(config.instance.center, zoom);

        var query = parseQueryString()['q'];
        var initialSearch = {};
        if (query) {
            initialSearch = JSON.parse(query);
        }

        // Use a bus to delay sending the initial signal
        // seems like you could merge with Bacon.once(initialSearch)
        // but that empirically doesn't work

        var initialQueryBus = new Bacon.Bus();
        var builtSearchEvents = searchEventStream
                .map(Search.buildSearch)
                .merge(initialQueryBus);

        Search.init(builtSearchEvents, config, function (filter) {
            plotLayer.setFilter(filter);
            utfLayer.setFilter(filter);
        });

        initialQueryBus.push(initialSearch);

    }
};
