"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bootstrap = require('bootstrap'),  // for $(...).collapse()
    Bacon = require('baconjs'),
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

$('[data-action="addtree"]').click(function(e) {
    e.preventDefault();
    modes.activateAddTreeMode();
});

$('[data-action="addresource"]').click(function(e) {
    e.preventDefault();
    modes.activateAddResourceMode();
});

Search.init(
    ecoBenefitsSearchEvents,
    _.bind(mapManager.setFilter, mapManager));

buttonEnabler.run();

modes.init(mapManager, triggerSearchFromSidebar);

// Read state from current URL, initializing zoom/lat/long/search/mode
mapPage.initMapState();
