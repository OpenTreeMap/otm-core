"use strict";

// Shared functionality for pages with a big map

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    url = require('url'),
    L = require('leaflet'),
    U = require('treemap/lib/utility.js'),
    MapManager = require('treemap/lib/MapManager.js'),
    mapManager = new MapManager(),
    urlState = require('treemap/lib/urlState.js'),
    SearchBar = require('treemap/lib/searchBar.js'),
    config = require('treemap/lib/config.js'),
    boundarySelect = require('treemap/lib/boundarySelect.js');

$.ajaxSetup(require('treemap/lib/csrf.js').jqueryAjaxSetupOptions);

module.exports.init = function (options) {
    // init mapManager before searchBar so that .setCenterWM is set
    var zoomLatLngOutputStream = mapManager.createTreeMap(options);

    // When there is a single geocode result (either by an exact match
    // or the user selects a candidate) move the map to it and zoom
    // if the map is not already zoomed in.
    var searchBar = SearchBar.init();

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
            searchBar.filterNonGeocodeObjectStream,
            geocodeEvents);

    triggeredQueryStream.onValue(searchBar.applySearchToDom);

    if (options.saveSearchInUrl) {
        builtSearchEvents.onValue(urlState.setSearch);
    }

    searchBar.searchChangedStream.onValue(function () {
        clearFoundLocationMarker(mapManager.map);
    });

    boundarySelect.init({
        idStream: builtSearchEvents.map(searchToBoundaryId),
        map: mapManager.map,
        style: options.fillSearchBoundary ? {
            fillOpacity: 0.3,
            fillColor: config.instance.secondaryColor || '#56abb2'
        } : {
            fillOpacity: 0
        }
    });

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

function onLocationFound(mapManager, location) {
    var latLng = U.webMercatorToLeafletLatLng(location.x, location.y),
        marker = L.marker(latLng, {
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
