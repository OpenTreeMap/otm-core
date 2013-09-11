"use strict";

var $ = require('jquery'),
    Bootstrap = require('bootstrap'),  // for $(...).collapse()
    Bacon = require('baconjs'),
    U = require('./utility'),
    csrf = require('./csrf'),

    mapManager = require('./mapManager'),
    Search = require('./search'),
    otmTypeahead = require('./otmTypeahead'),
    modes = require('./modeManagerForMapPage'),
    geocoder = require('./geocoder'),
    geocoderUi = require('./GeocoderUi'),
    BU = require('./baconUtils');

var app = {
    initSearchUi: function(config) {
        otmTypeahead.create({
            name: "species",
            url: config.instance.url + "species",
            input: "#species-typeahead",
            template: "#species-element-template",
            hidden: "#search-species",
            reverse: "id"
        });
        otmTypeahead.create({
            name: "boundaries",
            url: config.instance.url + "boundaries",
            input: "#boundary-typeahead",
            template: "#boundary-element-template",
            hidden: "#boundary",
            reverse: "id"
        });
        $("#search-advanced").on("click", function() {
            $("#advanced-search-pane").toggle(0); // Show/hide with 0 animation time
        });
    },

    unmatchedBoundarySearchValue: function() {
        return $('#boundary-typeahead').attr('data-unmatched');
    },

    resetEventStream: function() {
        return $("#search-reset").asEventStream("click");
    },

    cancelGeocodeSuggestionStream: function() {
        // Hide suggestion list if user edits search text or resets search
        return $('#boundary-typeahead').asEventStream('keyup')
            .merge(app.resetEventStream())
    },

    searchEventStream: function() {
        var enterKeyPressStream = $('input[data-class="search"]')
                .asEventStream("keyup")
                .filter(BU.isEnterKey),

            performSearchClickStream = $("#perform-search")
                .asEventStream("click"),

            triggerEventStream = enterKeyPressStream.merge(
                performSearchClickStream);

        return triggerEventStream;
    },

    redirectToSearchPage: function (config, query) {
        query = U.getUpdatedQueryString('q', JSON.stringify(query));

        window.location.href =
            config.instance.url + 'map/?' + query;
    },

    showGeocodeError: function (e) {
        if (e.status && e.status === 404) {
            // TODO: Toast
            window.alert('There were no results matching your search.');
        } else {
            // TODO: Toast
            window.alert('There was a problem running your search.');
        }
    }
};

module.exports = {
    init: function (config) {
        app.resetEventStream()
            .onValue(Search.reset);

        app.initSearchUi(config);

        app.searchEventStream()
            .map(Search.buildSearch)
            .onValue(app.redirectToSearchPage, config);
    },

    initMapPage: function (config) {
        var searchEventStream = app.searchEventStream(),
            resetStream = app.resetEventStream();

        // If a search is submitted with a boundary value that does
        // not match any autocomplete value, run it through the geocoder
        var geocodeResponseStream = 
            geocoder(config).geocodeStream(
                searchEventStream.map(app.unmatchedBoundarySearchValue)
                                 .filter(BU.isDefinedNonEmpty)
            );

        var geocodedLocationStream = geocoderUi(
            {
                geocodeResponseStream: geocodeResponseStream,
                cancelGeocodeSuggestionStream: app.cancelGeocodeSuggestionStream(),
                resultTemplate: '#geocode-results-template',
                addressInput: '#boundary-typeahead',
                displayedResults: '.search-block [data-class="geocode-result"]'
            });

        // When there is a single geocode result (either by an exact match
        // or the user selects a candidate) move the map to it and zoom
        // if the map is not already zoomed in.
        geocodedLocationStream.onValue(function (result) {
            mapManager.setCenterAndZoomIn(result.coordinates, mapManager.ZOOM_PLOT);
        });

        // Let the user know if there was a problem geocoding
        geocodeResponseStream.onError(app.showGeocodeError);
        //geocoderUi.errorStream.onValue(app.showGeocodeError);

        // Set up cross-site forgery protection
        $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

        app.initSearchUi(config);

        mapManager.init({
            config: config,
            selector: '#map'
        });
        modes.init(config, mapManager);
        modes.activateBrowseTreesMode();

        $('.addBtn').click(modes.activateAddTreeMode);

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

        Search.init(builtSearchEvents, config, mapManager.setFilter);

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
