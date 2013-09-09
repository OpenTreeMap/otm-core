"use strict";

var $ = require('jquery'),
    Bootstrap = require('bootstrap'),
    Bacon = require('baconjs'),
    U = require('./utility'),
    csrf = require('./csrf'),
    mustache = require('mustache'),

    mapManager = require('./mapManager'),
    Search = require('./search'),
    otmTypeahead = require('./otmTypeahead'),
    modes = require('./modeManagerForMapPage'),
    geocoder = require('./geocoder'),
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

    selectGeocodeCandidateStream: function() {
        // The search results are added to the page dynamically so
        // we need to use a live-style selector.
        return $("body").asEventStream('click', 
            '[data-class="geocode-result"]', function (e, args) { 
                var $result = $(e.target);
                return {
                    x: $result.data('x'),
                    y: $result.data('y'),
                    coordinates: [$result.data('x'),  $result.data('y')],
                    address: $result.data('address')
                };
            });
        // return $('[data-class="geocode-result"]').asEventStream('click');
    },

    cancelGeocodeSuggestionStream: function() {
        // Hide the suggestion list if...
        return Bacon.mergeAll([
            // the user edits the search text
            $('#boundary-typeahead').asEventStream('keyup'),
            // the suggestion list if the user resets the search
            app.resetEventStream(),
            // the user selects a suggestion
            app.selectGeocodeCandidateStream()
        ]);
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

    // `showGeocodeCandidates` displays a list of geocode candidates
    // as a popover under the search text box.
    showGeocodeCandidates: function (map, template, res) {
        if (res.candidates) {
            $('#boundary-typeahead').popover({
                html: true, // Allows 'content' to be markup
                content: template(res),
                placement: 'bottom',
                trigger: 'manual',
                title: 'Results'
            }).popover('show');
        } else {
            window.alert('There was a problem running your search.');
        }
    },

    showGeocodeError: function (e) {
        if (e.status && e.status === 404) {
            // TODO: Toast
            window.alert('There were no results matching your search.');
        } else {
            // TODO: Toast
            window.alert('There was a problem running your search.');
        }
    },

    geocodeResponseHasASingleCandidate: function (res) {
        return res && res.candidates && res.candidates.length === 1;
    },

    geocodeResponseHasMultipleCandidates: function (res) {
        return res && res.candidates && res.candidates.length > 1;
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

        var geocodeResultsTemplate = mustache.compile(
            $('#geocode-results-template').html());

        // If a search is submitted with a boundary value that does
        // not match any autocomplete value run it through the
        // geocoder
        var geocodeResponseStream = 
            geocoder(config).geocodeStream(
                searchEventStream.map(app.unmatchedBoundarySearchValue)
                                 .filter(BU.isDefinedNonEmpty)
            );

        // Get a stream of all geocode responses that have a single exact
        // match converted to a standard result object
        var singleGeocodeMatchStream = geocodeResponseStream
            .filter(app.geocodeResponseHasASingleCandidate)
            .map(function (res) {
                var match = res.candidates[0];
                match.coordinates = [match.x,  match.y];
                return match;
            });

        // When there is a single geocode result (either by an exact match
        // or the user selects a candidate) move the map to it and zoom
        // if the map is not already zoomed in.
        singleGeocodeMatchStream.merge(app.selectGeocodeCandidateStream())
            .onValue(function (result) {
                var map = mapManager.map;
                map.setCenter(result.coordinates, Math.max(map.getZoom(), 18));
            });

        // When there are multiple geocode results, show them to the
        // user.
        geocodeResponseStream
            .filter(app.geocodeResponseHasMultipleCandidates)
            .onValue(app.showGeocodeCandidates, mapManager.map, geocodeResultsTemplate);

        // Let the user know if there was a problem geocoding
        geocodeResponseStream.onError(app.showGeocodeError);

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

        // Connect geocode cancel events to destroying the suggestion popover
        app.cancelGeocodeSuggestionStream().onValue(function () {
            $('#boundary-typeahead').popover('hide').popover('destroy');
        });

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
