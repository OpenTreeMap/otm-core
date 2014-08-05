"use strict";

// Given a set of search input elements (text boxes) and a "search" button,
// Return a stream of "search" events triggered by hitting "Enter" in one of
// the input boxes or clicking the "search" button.

// There are two primary methods to use this module:
// 1) call .initDefaults() with a config, which sets up basic behavior.
// 2) call .init() and use the return object to bind events to the streams.

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    otmTypeahead = require('treemap/otmTypeahead'),
    U = require('treemap/utility'),
    geocoder = require('treemap/geocoder'),
    geocoderUi = require('treemap/geocoderUi'),
    Search = require('treemap/search'),
    udfcSearch = require('treemap/udfcSearch'),
    BU = require('treemap/baconUtils'),
    MapManager = require('treemap/MapManager'),
    mapManager = new MapManager();

// Placed onto the jquery object
require('bootstrap-datepicker');

var showGeocodeError = function (e) {
    // Bacon just returns an error string
    if (_.isString(e)) {
        // TODO: Toast
        window.alert(e);
    // If there was an error from the server the error
    // object contains standard http info
    } else if (e.status && e.status === 404) {
        // TODO: Toast
        window.alert('There were no results matching your search.');
    } else {
        // TODO: Toast
        window.alert('There was a problem running your search.');
    }
};

var unmatchedBoundarySearchValue = function() {
    return $('#boundary-typeahead').attr('data-unmatched');
};

function redirectToSearchPage(config, filters, wmCoords) {
    var getZPortion = function (wmCoords) {
            var ll = U.webMercatorToLatLng(wmCoords.x, wmCoords.y);
            return '&z='+ mapManager.ZOOM_PLOT + '/' + ll.lat + '/' + ll.lng;
        },
        query = Search.makeQueryStringFromFilters(config, filters);

    query += wmCoords ? getZPortion(wmCoords) : '';

    window.location.href = config.instance.url + 'map/?' + query;
}

function initSearchUi(config, searchStream) {
    var $advancedToggle = $("#search-advanced"),
        $subheader = $(".subhead");
    otmTypeahead.create({
        name: "species",
        url: config.instance.url + "species/",
        input: "#species-typeahead",
        template: "#species-element-template",
        hidden: "#search-species",
        button: "#species-toggle",
        reverse: "id",
        forceMatch: true
    });
    otmTypeahead.create({
        name: "boundaries",
        url: config.instance.url + "boundaries/",
        input: "#boundary-typeahead",
        template: "#boundary-element-template",
        hidden: "#boundary",
        button: "#boundary-toggle",
        reverse: "id",
        sortKeys: ['sortOrder', 'value']
    });

    // hide advanced search dropdown when search is executed
    searchStream.onValue(function () {
        if ($advancedToggle.hasClass('active')) {
            $advancedToggle.removeClass('active').blur();
        }
        if ($subheader.hasClass('expanded')) {
            $subheader.removeClass('expanded');
        }
    });

    $advancedToggle.on("click", function() {
        $advancedToggle.toggleClass('active').blur();
        $subheader.toggleClass('expanded');
    });
    $subheader.find("input[data-date-format]").datepicker();
}

module.exports = exports = {

    initDefaults: function (config) {
        var streams = exports.init(config),
            redirect = _.partial(redirectToSearchPage, config),
            redirectWithoutLocation = _.partialRight(redirect, undefined);

        streams.filterNonGeocodeObjectStream.onValue(redirectWithoutLocation);
        streams.geocodedLocationStream.onValue(function (wmCoords) {
            // get the current state of the search dom
            var filters = Search.buildSearch();
            redirect(filters, wmCoords);
        });

        streams.resetStream.onValue(Search.reset);

        // Apply an empty search to the page to get all the UI elements into
        // the correct state
        Search.reset();
    },

    init: function (config) {
        var searchStream = BU.enterOrClickEventStream({
                inputs: 'input[data-class="search"]',
                button: '#perform-search'
            }),
            resetStream = $("#search-reset").asEventStream("click"),
            filtersStream = searchStream
                .map(unmatchedBoundarySearchValue)
                .filter(BU.isUndefinedOrEmpty)
                .map(Search.buildSearch),
            uSearch = udfcSearch.init(resetStream),

            geocoderInstance = geocoder(config),
            geocodeCandidateStream = searchStream.map(unmatchedBoundarySearchValue).filter(BU.isDefinedNonEmpty),
            geocodeResponseStream = geocoderInstance.geocodeStream(geocodeCandidateStream),
            geocodedLocationStream = geocoderUi(
                {
                    geocodeResponseStream: geocodeResponseStream,
                    cancelGeocodeSuggestionStream: resetStream,
                    resultTemplate: '#geocode-results-template',
                    addressInput: '#boundary-typeahead',
                    displayedResults: '.search-block [data-class="geocode-result"]'
                });

        geocodeResponseStream.onError(showGeocodeError);
        initSearchUi(config, searchStream);


        return {
            // a stream events corresponding to clicks on the reset button.
            resetStream: resetStream,

            // the final, pinpointed stream of geocoded locations
            // consumers should act with this data directly to
            // modify the state of their UI or pass to other consumers.
            geocodedLocationStream: geocodedLocationStream,

            // Stream of search events, carries the filter object and display
            // list with it. should be used by consumer to execute searches.
            filterNonGeocodeObjectStream: filtersStream,

            applySearchToDom: function (search) {
                Search.applySearchToDom(search);
                uSearch.applyFilterObjectToDom(search);
            }
        };
    }
};
