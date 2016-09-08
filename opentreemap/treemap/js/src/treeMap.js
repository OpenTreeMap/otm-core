"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bootstrap = require('bootstrap'),  // for $(...).collapse()
    Bacon = require('baconjs'),
    url = require('url'),
    addTreeModeName = require('treemap/lib/addTreeMode.js').name,
    addResourceModeName = require('treemap/lib/addResourceMode.js').name,
    BU = require('treemap/lib/baconUtils.js'),
    buttonEnabler = require('treemap/lib/buttonEnabler.js'),
    MapPage = require('treemap/lib/mapPage.js'),
    modes = require('treemap/lib/treeMapModes.js'),
    Search = require('treemap/lib/search.js');

function changeMode (modeName) {
    if (modeName === addTreeModeName) {
        modes.activateAddTreeMode();
    } else if (modeName === addResourceModeName) {
        modes.activateAddResourceMode();
    } else {
        modes.activateBrowseTreesMode();
    }
}

var mapPage = MapPage.init({
        domId: 'map',
        trackZoomLatLng: true
    }),
    mapManager = mapPage.mapManager,

    triggerSearchFromSidebar = new Bacon.Bus(),

    ecoBenefitsSearchEvents =
        Bacon.mergeAll(
            mapPage.builtSearchEvents,
            triggerSearchFromSidebar.map(mapPage.getMapStateSearch)
        ),

    modeChangeStream = mapPage.mapStateChangeStream
        .map('.modeName')
        .filter(BU.isDefined);

modeChangeStream.onValue(changeMode);

var performAdd = function (e, addFn) {
    if (!mapPage.embed) {
        e.preventDefault();
        addFn();
    } else {
        var btn = e.target,
            href = btn.href,
            parsedHref = url.parse(href, true),
            currentLocation = url.parse(location.href, true),
            adjustedQuery = _.chain({})
                .assign(currentLocation.query, parsedHref.query)
                .omit('embed')
                .value();
        parsedHref.search = null;
        parsedHref.query = adjustedQuery;
        btn.href = url.format(parsedHref);
        // allow default
    }
};

$('[data-action="addtree"]').click(function(e) {
    performAdd(e, modes.activateAddTreeMode);
});

$('[data-action="addresource"]').click(function(e) {
    performAdd(e, modes.activateAddResourceMode);
});

Search.init(
    ecoBenefitsSearchEvents,
    _.bind(mapManager.setFilter, mapManager));

buttonEnabler.run();

modes.init(mapManager, triggerSearchFromSidebar, mapPage.embed);

// Read state from current URL, initializing zoom/lat/long/search/mode
mapPage.initMapState();
