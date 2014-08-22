"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bootstrap = require('bootstrap'),  // for $(...).collapse()
    Bacon = require('baconjs'),
    addTreeModeName = require('treemap/addTreeMode').name,
    addResourceModeName = require('treemap/addResourceMode').name,
    BU = require('treemap/baconUtils'),
    buttonEnabler = require('treemap/buttonEnabler'),
    MapPage = require('treemap/mapPage'),
    modes = require('treemap/treeMapModes'),
    Search = require('treemap/search');

function changeMode (modeName) {
    if (modeName === addTreeModeName) {
        modes.activateAddTreeMode();
    } else if (modeName === addResourceModeName) {
        modes.activateAddResourceMode();
    } else {
        modes.activateBrowseTreesMode();
    }
}

module.exports.init = function (config) {
    var mapPage = MapPage.init({
            config: config,
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
        config,
        _.bind(mapManager.setFilter, mapManager));

    buttonEnabler.run({ config: config });

    modes.init(config, mapManager, triggerSearchFromSidebar);

    // Read state from current URL, initializing zoom/lat/long/search/mode
    mapPage.initMapState();
};
