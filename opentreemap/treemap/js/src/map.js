"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bootstrap = require('bootstrap'),  // for $(...).collapse()
    Bacon = require('baconjs'),
    L = require('leaflet'),
    csrf = require('treemap/csrf'),

    mapManager = require('treemap/mapManager'),
    addTreeModeName = require('treemap/addTreeMode').name,
    addResourceModeName = require('treemap/addResourceMode').name,
    mapState = require('treemap/mapState'),
    Search = require('treemap/search'),
    SearchBar = require('treemap/searchBar'),
    modes = require('treemap/modeManagerForMapPage'),
    boundarySelect = require('treemap/boundarySelect'),
    BU = require('treemap/baconUtils'),
    buttonEnabler = require('treemap/buttonEnabler');

// Map-page specific search code here

// ``searchToBoundaryId`` takes a JSON search object and
// extracts the numeric region ID included in the search.
// If a region is not specified in the search object
// ``searchToBoundaryId`` returns undefined.
var searchToBoundaryId = function(search) {
    if (!_.isUndefined(search) && !_.isUndefined(search.filter) && search.filter['mapFeature.geom']) {
        return parseFloat(search.filter['mapFeature.geom'].IN_BOUNDARY, 10);
    } else {
        return undefined;
    }
};

function changeMode (modeName) {
    if (modeName === addTreeModeName) {
        modes.activateAddTreeMode();
    } else if (modeName === addResourceModeName) {
        modes.activateAddResourceMode();
    } else {
        modes.activateBrowseTreesMode();
    }
}

function deserializeZoomLatLngAndSetOnMap (state) {
    var zll = state.zoomLatLng,
        center = new L.LatLng(zll.lat, zll.lng);
    mapManager.setCenterAndZoomLL(zll.zoom, center);
}

function serializeZoomLatLngFromMap () {
    var zoom = mapManager.map.getZoom(),
        center = mapManager.map.getCenter();
    mapState.setZoomLatLng(zoom, center);
}

module.exports = {
    initMapPage: function (config) {

        var triggerSearchFromSidebar = new Bacon.Bus();

        // init mapManager before searchBar so that .setCenterWM is set
        mapManager.init({ config: config, selector: '#map' });


        // When there is a single geocode result (either by an exact match
        // or the user selects a candidate) move the map to it and zoom
        // if the map is not already zoomed in.
        var bar = SearchBar.init(config);

        bar.geocodedLocationStream.onValue(mapManager.setCenterWM);

        var zoomLatLngStream = mapState.stateChangeStream.filter('.zoomLatLng');

        zoomLatLngStream.onValue(deserializeZoomLatLngAndSetOnMap);

        var triggeredQueryStream =
            Bacon.mergeAll(
                mapState.stateChangeStream // URL changed
                    .filter('.search')     // search changed
                    .map('.search'),       // get search string
                bar.resetStream.map({})
            );

        var builtSearchEvents =
            Bacon.mergeAll(triggeredQueryStream, bar.filterNonGeocodeObjectStream);

        var ecoBenefitsSearchEvents =
            Bacon.mergeAll(
                builtSearchEvents,
                triggerSearchFromSidebar.map(mapState.getSearch)
            );

        triggeredQueryStream.onValue(Search.applySearchToDom);

        builtSearchEvents.onValue(mapState.setSearch);

        var modeChangeStream = mapState.stateChangeStream
                .map('.modeName')
                .filter(BU.isDefined);

        modeChangeStream.onValue(changeMode);

        $('[data-action="addtree"]').click(function(e) {
            e.preventDefault();
            modes.activateAddTreeMode();
        });

        $('[data-action="addresource"]').click(function(e) {
            e.preventDefault();
            modes.activateAddResourceMode();
        });

        $.ajaxSetup(csrf.jqueryAjaxSetupOptions);


        mapManager.map.on("moveend", serializeZoomLatLngFromMap);

        Search.init(ecoBenefitsSearchEvents, config, mapManager.setFilter);


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

        // Reads state from current URL, possibly triggering
        // updates via mapState.stateChangeStream
        mapState.init();
    }
};
