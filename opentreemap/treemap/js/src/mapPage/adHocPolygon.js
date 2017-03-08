"use strict";

var $ = require('jquery'),
    _ = require('lodash');

var dom = {
    cancelDrawArea: '.cancel-draw-area',
    clearLocationSearch: '.clear-location-search',
    drawAreaButton: '.draw-area-button',
    controls: {
        standard: '#location-search-well',
        drawArea: '#draw-area-controls',
        customArea: '#custom-area-controls',
        editArea: '#edit-area-controls'
    }
};

var map,
    modes,
    adHocPolygonLayer;

function init(options) {
    map = options.map;
    modes = options.modes;

    $(dom.drawAreaButton).click(modes.activateDrawAreaMode);
    $(dom.cancelDrawArea).click(cancelDrawArea);
    $(dom.clearLocationSearch).click(clearLocationSearch);
}

function cancelDrawArea() {
    clearLocationSearch();
    modes.activateBrowseTreesMode(true);
}

function clearLocationSearch() {
    // Note this may be called from any mode, not just drawAreaMode
    if (adHocPolygonLayer) {
        map.removeLayer(adHocPolygonLayer);
        adHocPolygonLayer = null;
    }
    showControls(dom.controls.standard);
}

function onActivate() {
    showControls(dom.controls.drawArea);
    $(document).on('keydown', onKeyDown);
}

function onKeyDown(e) {
    if (e.keyCode == 27) {  // Escape key
        cancelDrawArea();
    }
}

function onNewPolygon(polygonLayer) {
    adHocPolygonLayer = polygonLayer.addTo(map);
    modes.activateBrowseTreesMode(true);
}

function onDeactivate() {
    showControls(adHocPolygonLayer ? dom.controls.customArea : dom.controls.standard);
    $(document).off('keydown', onKeyDown);
}

function showControls(controls) {
    _.each(dom.controls, function (c) {
        $(c).hide();
    });
    $(controls).show();
}

module.exports = {
    init: init,
    onActivate: onActivate,
    onNewPolygon: onNewPolygon,
    onDeactivate: onDeactivate
};
