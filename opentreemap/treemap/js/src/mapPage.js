"use strict";

// Shared functionality for pages with a big map

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    L = require('leaflet'),
    BU = require('treemap/baconUtils'),
    MapManager = require('treemap/MapManager'),
    mapManager = new MapManager(),
    urlState = require('treemap/urlState'),
    SearchBar = require('treemap/searchBar'),
    boundarySelect = require('treemap/boundarySelect');

$.ajaxSetup(require('treemap/csrf').jqueryAjaxSetupOptions);

module.exports.init = function (options) {
    var config = options.config;

    // init mapManager before searchBar so that .setCenterWM is set
    mapManager.createTreeMap(options);

    // When there is a single geocode result (either by an exact match
    // or the user selects a candidate) move the map to it and zoom
    // if the map is not already zoomed in.
    var searchBar = SearchBar.init(config);

    searchBar.geocodedLocationStream.onValue(mapManager, 'setCenterWM');

    var triggeredQueryStream =
        Bacon.mergeAll(
            urlState.stateChangeStream // URL changed
                .filter('.search')     // search changed
                .map('.search'),       // get search string
            searchBar.resetStream.map({})
        );

    var builtSearchEvents = Bacon.mergeAll(
            triggeredQueryStream,
            searchBar.filterNonGeocodeObjectStream);

    triggeredQueryStream.onValue(searchBar.applySearchToDom);

    builtSearchEvents.onValue(urlState.setSearch);

    boundarySelect.init({
        config: config,
        idStream: builtSearchEvents.map(searchToBoundaryId),
        map: mapManager.map,
        style: {
            fillOpacity: 0.3,
            fillColor: config.instance.secondaryColor || '#56abb2'
        }
    });

    return {
        mapManager: mapManager,
        map: mapManager.map,
        builtSearchEvents: builtSearchEvents,
        getMapStateSearch: urlState.getSearch,
        mapStateChangeStream: urlState.stateChangeStream,
        initMapState: urlState.init
    };
};

// Extract and return numeric region ID from JSON search object, or
// return undefined if a region is not specified in the search object.
function searchToBoundaryId(search) {
    if (!_.isUndefined(search) && !_.isUndefined(search.filter) && search.filter['mapFeature.geom']) {
        return parseFloat(search.filter['mapFeature.geom'].IN_BOUNDARY, 10);
    } else {
        return undefined;
    }
}
