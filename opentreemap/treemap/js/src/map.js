"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    Bootstrap = require('bootstrap'),  // for $(...).collapse()
    Bacon = require('baconjs'),
    U = require('./utility'),
    csrf = require('./csrf'),

    mapManager = require('./mapManager'),
    addTreeMode = require('./addTreeMode'),
    Search = require('./search'),
    searchBar = require('./searchBar'),
    modes = require('./modeManagerForMapPage'),
    geocoder = require('./geocoder'),
    geocoderUi = require('./geocoderUi'),
    boundarySelect = require('./boundarySelect'),
    BU = require('./baconUtils');

// Map-page specific search code here
var unmatchedBoundarySearchValue = function() {
    return $('#boundary-typeahead').attr('data-unmatched');
};

var showGeocodeError = function (e) {
    if (e.status && e.status === 404) {
        // TODO: Toast
        window.alert('There were no results matching your search.');
    } else {
        // TODO: Toast
        window.alert('There was a problem running your search.');
    }
};

// ``searchToBoundaryId`` takes a JSON search object and
// extracts the numeric region ID included in the search.
// If a region is not specified in the search object
// ``searchToBoundaryId`` returns undefined.
var searchToBoundaryId = function(search) {
    if (search !== undefined && search['plot.geom']) {
        return parseFloat(search['plot.geom'].IN_BOUNDARY, 10);
    } else {
        return undefined;
    }
};

module.exports = {
    initMapPage: function (config) {
        var searchEventStream = searchBar.searchEventStream(),
            resetStream = searchBar.resetEventStream(),
            elems = searchBar.getElems();

        // If a search is submitted with a boundary value that does
        // not match any autocomplete value, run it through the geocoder
        var geocodeResponseStream =
            geocoder(config).geocodeStream(
                searchEventStream.map(unmatchedBoundarySearchValue)
                                 .filter(BU.isDefinedNonEmpty)
            );

        var geocodedLocationStream = geocoderUi(
            {
                geocodeResponseStream: geocodeResponseStream,
                cancelGeocodeSuggestionStream: searchBar.resetEventStream(),
                resultTemplate: '#geocode-results-template',
                addressInput: '#boundary-typeahead',
                displayedResults: '.search-block [data-class="geocode-result"]'
            });

        // When there is a single geocode result (either by an exact match
        // or the user selects a candidate) move the map to it and zoom
        // if the map is not already zoomed in.
        geocodedLocationStream.onValue(function (location) {
            mapManager.setCenterAndZoomIn(location, mapManager.ZOOM_PLOT);
        });

        // Let the user know if there was a problem geocoding
        geocodeResponseStream.onError(showGeocodeError);

        // Set up cross-site forgery protection
        $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

        searchBar.initSearchUi(config);

        var triggerSearchFromSidebar = new Bacon.Bus();

        mapManager.init({
            config: config,
            selector: '#map'
        });
        modes.init(config, mapManager, triggerSearchFromSidebar);
        if (window.location.hash === addTreeMode.hash) {
            modes.activateAddTreeMode();
        } else {
            modes.activateBrowseTreesMode();
        }

        $('[data-action="addtree"]').click(function(e) {
            e.preventDefault();
            modes.activateAddTreeMode();
        });

        var triggerSearchFromUrl = new Bacon.Bus();

        var initialQueryBus = triggerSearchFromUrl
            .map(U.getCurrentFilterString)
            .skipDuplicates()
            .map(JSON.parse);

        var repeatableQueryBus = triggerSearchFromSidebar
            .map(U.getCurrentFilterString)
            .map(JSON.parse);

        var triggeredQueryBus = resetStream.map({})
                                           .merge(initialQueryBus);

        window.addEventListener('popstate', function(event) {
            triggerSearchFromUrl.push();
        }, false);

        var builtSearchEvents = searchEventStream
                .map(Search.buildSearch, elems)
                .merge(triggeredQueryBus);

        var ecoBenefitsSearchEvents = builtSearchEvents.merge(repeatableQueryBus);

        boundarySelect.init({
            config: config,
            idStream: builtSearchEvents.map(searchToBoundaryId),
            map: mapManager.map,
            style: {
                fillOpacity: 0.3,
                fillColor: config.instance.secondaryColor || '#56abb2'
            }
        });

        triggeredQueryBus.onValue(Search.applySearchToDom, elems);

        Search.init(ecoBenefitsSearchEvents, config, mapManager.setFilter);

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

        triggerSearchFromUrl.push();
    }
};
