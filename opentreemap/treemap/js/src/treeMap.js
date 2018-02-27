"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bootstrap = require('bootstrap'),  // for $(...).collapse()
    Bacon = require('baconjs'),
    url = require('url'),
    addTreeModeName = require('treemap/mapPage/addTreeMode.js').name,
    addResourceModeName = require('treemap/mapPage/addResourceMode.js').name,
    BU = require('treemap/lib/baconUtils.js'),
    buttonEnabler = require('treemap/lib/buttonEnabler.js'),
    MapPage = require('treemap/lib/mapPage.js'),
    modes = require('treemap/mapPage/modes.js'),
    Search = require('treemap/lib/search.js');

var mapPage = MapPage.init({
        domId: 'map',
        trackZoomLatLng: true,
        fillSearchBoundary: true,
        saveSearchInUrl: true,
        shouldUseLocationSearchUI: true
    }),
    mapManager = mapPage.mapManager,

    triggerSearchFromSidebar = new Bacon.Bus(),

    searchEvents =
        Bacon.mergeAll(
            mapPage.builtSearchEvents,
            triggerSearchFromSidebar.map(mapPage.getMapStateSearch)
        ),

    modeChangeStream = mapPage.mapStateChangeStream
        .filter(BU.isPropertyDefined('modeName')),

    completedSearchStream = Search.init(
        searchEvents,
        _.bind(mapManager.setFilter, mapManager));


modeChangeStream.onValue(function (modeOptions) {
    // Mode was specified in the URL, e.g. because user clicked "Add a Tree" on
    // a different page
    var modeName = modeOptions.modeName,
        mapFeatureType = modeOptions.modeType;

    if (modeName === addTreeModeName) {
        modes.activateAddTreeMode();
    } else if (modeName === addResourceModeName) {
        modes.activateAddResourceMode({mapFeatureType: mapFeatureType});
    } else {
        modes.activateBrowseTreesMode();
    }
});

$('[data-action="addtree"]').on('click', function(e) {
    performAdd(e, modes.activateAddTreeMode);
});

$('[data-action="addresource"]').on('click', function(e) {
    performAdd(e, modes.activateAddResourceMode);
});

var performAdd = function (e, activateTheMode) {
    var btn = e.target;

    if (!mapPage.embed) {
        var mapFeatureType = $(btn).attr('data-class');
        e.preventDefault();
        activateTheMode({mapFeatureType: mapFeatureType});
    } else {
        var href = btn.href,
            parsedHref = url.parse(href, true),
            currentLocation = url.parse(location.href, true),
            adjustedQuery = _({})
                .assign(currentLocation.query, parsedHref.query)
                .omit('embed')
                .value();
        parsedHref.search = null;
        parsedHref.query = adjustedQuery;
        btn.href = url.format(parsedHref);
        // allow default
    }
};

buttonEnabler.run();

modes.init(mapManager, triggerSearchFromSidebar, mapPage.embed,
    completedSearchStream);

// Read state from current URL, initializing
// zoom/lat/long/search/mode/selection
mapPage.initMapState();

// Toggle class on panel-group when toggle is tapped to show/hide
// expanded view on mobile
var prevCenter;
$('#feature-panel').on('click', '.sidebar-panel-toggle', function() {
    $('body').toggleClass('hide-search open');
    $('#feature-panel').toggleClass('expanded with-map');

    // Recenter map on selected feature when shrinking it
    // Put it back to previous center when enlarging it again
    var latLon = prevCenter;
    if ($('body').is('.open')) {
        prevCenter = mapPage.map.getCenter();
        latLon = $("#map-feature-popup").data('latlon');
    }
    mapPage.map.invalidateSize();
    mapPage.map.panTo(latLon, {
        animate: true,
        duration: 0.4,
        easeLinearity: 0.1
    });
});

$('#eco-panel').on('click', '.sidebar-panel-toggle', function() {
    $('#eco-panel').toggleClass('expanded full');
});
