"use strict";

// Shared functionality for pages with a big map

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    url = require('url'),
    L = require('leaflet'),
    MapManager = require('treemap/lib/MapManager.js'),
    mapManager = new MapManager(),
    urlState = require('treemap/lib/urlState.js'),
    SearchBar = require('treemap/lib/searchBar.js'),
    config = require('treemap/lib/config.js'),
    boundarySelect = require('treemap/lib/boundarySelect.js'),
    locationSearchUI = require('treemap/mapPage/locationSearchUI.js');

$.ajaxSetup(require('treemap/lib/csrf.js').jqueryAjaxSetupOptions);

module.exports.init = function (options) {
    // init mapManager before searchBar so that .setCenterWM is set
    var zoomLatLngOutputStream = mapManager.createTreeMap(options);

    var customAreaSearchEvents = options.shouldUseLocationSearchUI &&
        locationSearchUI.init({
            mapManager: mapManager
        }) || null;

    var searchBar = SearchBar.init({
        customAreaSearchEvents: customAreaSearchEvents
    });

    // When there is a geocode result, move the map to it and zoom
    // (if the map is not already zoomed in).
    searchBar.geocodedLocationStream.onValue(_.partial(onLocationFound, mapManager));

    var triggeredQueryStream =
        Bacon.mergeAll(
            urlState.stateChangeStream // URL changed
                .filter('.search')     // search changed
                .map('.search'),       // get search string
            searchBar.resetStream.map({})
        );

    var geocodeEvents = searchBar.searchFiltersProp
        .sampledBy(searchBar.geocodedLocationStream);

    var builtSearchEvents = Bacon.mergeAll(
            triggeredQueryStream,
            searchBar.filtersStream,
            geocodeEvents);

    if (options.shouldUseLocationSearchUI) {
        // When loading the page from a URL with a BOUNDARY_ID search,
        // we must wait for the location typeahead to populate the
        // "Search by Location" input box (by fetching the boundary name
        // from the server).
        //
        // That triggers an event on searchBar.programaticallyUpdatedStream,
        // and we call locationSearchUI.onSearchChanged,
        // which uses the presence of text in the "Search by Location" input box
        // to distinguish between named and anonymous boundaries.
        builtSearchEvents
            .merge(searchBar.programmaticallyUpdatedStream)
            .onValue(locationSearchUI.onSearchChanged);
        searchBar.resetStream.onValue(function () {
            locationSearchUI.clearCustomArea();
        });
    }

    triggeredQueryStream.onValue(searchBar.applySearchToDom);

    if (options.saveSearchInUrl) {
        builtSearchEvents.onValue(urlState.setSearch);
    }

    searchBar.searchChangedStream.onValue(function () {
        clearFoundLocationMarker(mapManager.map);
    });

    var boundaryLayerStream = boundarySelect.init({
        idStream: builtSearchEvents.map(searchToBoundaryId),
        map: mapManager.map,
        style: options.fillSearchBoundary ? {
            fillOpacity: 0.3,
            fillColor: config.instance.secondaryColor || '#56abb2'
        } : {
            fillOpacity: 0
        }
    });

    if (options.shouldUseLocationSearchUI) {
        boundaryLayerStream.onValue(locationSearchUI.removeDrawingLayer);
    }

    var queryObject = url.parse(location.href, true).query;
    var embed = queryObject && queryObject.hasOwnProperty('embed');

    return {
        mapManager: mapManager,
        map: mapManager.map,
        embed: !!embed,
        builtSearchEvents: builtSearchEvents,
        getMapStateSearch: urlState.getSearch,
        mapStateChangeStream: urlState.stateChangeStream,
        zoomLatLngOutputStream: zoomLatLngOutputStream,
        initMapState: urlState.init
    };
};

function onLocationFound(mapManager, latLng) {
    var marker = L.marker(latLng, {
            icon: L.icon({
                iconUrl: config.staticUrl + 'img/mapmarker_locationsearch.png',
                iconSize: [70, 60],
                iconAnchor: [20, 60]
            }),
            clickable: false,
            keyboard: false
        });
    marker.addTo(mapManager.map);
    mapManager.map.foundLocationMarker = marker;
    mapManager.setCenterLL(latLng);
}

function clearFoundLocationMarker(map) {
    if (map.foundLocationMarker) {
        map.removeLayer(map.foundLocationMarker);
        map.foundLocationMarker = null;
    }
}

// Extract and return numeric region ID from JSON search object, or
// return undefined if a region is not specified in the search object.
function searchToBoundaryId(search) {
    if (!_.isUndefined(search) && !_.isUndefined(search.filter) && search.filter['mapFeature.geom']) {
        return parseFloat(search.filter['mapFeature.geom'].IN_BOUNDARY, 10);
    } else {
        return undefined;
    }
}
