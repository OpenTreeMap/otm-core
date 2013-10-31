"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    Bootstrap = require('bootstrap'),  // for $(...).collapse()
    Bacon = require('baconjs'),
    L = require('leaflet'),
    csrf = require('treemap/csrf'),

    mapManager = require('treemap/mapManager'),
    addTreeModeName = require('treemap/addTreeMode').name,
    mapState = require('treemap/mapState'),
    Search = require('treemap/search'),
    searchBar = require('treemap/searchBar'),
    modes = require('treemap/modeManagerForMapPage'),
    geocoder = require('treemap/geocoder'),
    geocoderUi = require('treemap/geocoderUi'),
    boundarySelect = require('treemap/boundarySelect'),
    BU = require('treemap/baconUtils'),
    buttonEnabler = require('treemap/buttonEnabler');

// Map-page specific search code here
var unmatchedBoundarySearchValue = function() {
    return $('#boundary-typeahead').attr('data-unmatched');
};

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

        var triggerSearchFromSidebar = new Bacon.Bus();

        mapState.stateChangeStream
            .filter('.zoomLatLng')
            .onValue(function (state) {
                var zll = state.zoomLatLng,
                    center = new L.LatLng(zll.lat, zll.lng);
                mapManager.map.setView(center, zll.zoom);
            });

        mapState.stateChangeStream
            .map('.modeName')
            .filter(BU.isDefined)
            .onValue(function (modeName) {
                if (modeName === addTreeModeName) {
                    modes.activateAddTreeMode();
                } else {
                    modes.activateBrowseTreesMode();
                }
            });

        var triggeredQueryStream =
            Bacon.mergeAll(
                mapState.stateChangeStream // URL changed
                    .filter('.search')     // search changed
                    .map('.search'),       // get search string
                resetStream.map({})
            );

        var builtSearchEvents =
            Bacon.mergeAll(
                triggeredQueryStream,
                searchEventStream.map(Search.buildSearch, elems)
            );

        var ecoBenefitsSearchEvents =
            Bacon.mergeAll(
                builtSearchEvents,
                triggerSearchFromSidebar.map(mapState.getSearch)
            );

        triggeredQueryStream.onValue(Search.applySearchToDom, elems);

        builtSearchEvents.onValue(mapState.setSearch);

        $('[data-action="addtree"]').click(function(e) {
            e.preventDefault();
            modes.activateAddTreeMode();
        });

        $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

        mapManager.init({
            config: config,
            selector: '#map'
        });

        mapManager.map.on("moveend", function () {
            var zoom = mapManager.map.getZoom(),
                center = mapManager.map.getCenter();
            mapState.setZoomLatLng(zoom, center);
        });

        Search.init(ecoBenefitsSearchEvents, config, mapManager.setFilter);

        searchBar.initSearchUi(config);

        boundarySelect.init({
            config: config,
            idStream: builtSearchEvents.map(searchToBoundaryId),
            map: mapManager.map,
            style: {
                fillOpacity: 0.3,
                fillColor: config.instance.secondaryColor || '#56abb2'
            }
        });

        buttonEnabler.run({ config: config });

        modes.init(config, mapManager, triggerSearchFromSidebar);

        // Reads state from current URL, possibly triggering updates via mapState.stateChangeStream
        mapState.init();
    }
};
