"use strict";

var $ = require('jquery'),
    L = require('leaflet'),
    locationSearchUI = require('treemap/mapPage/locationSearchUI.js');

var map,
    modes,
    drawer,
    polygonComplete,
    originalTooltips,
    customTooltips;

var dom = {
    drawArea: '.draw-area',
    cancel: '.cancel-draw'
};

function init(options) {
    map = options.map;
    modes = options.modes;
    drawer = new L.Draw.Polygon(map);
    originalTooltips = L.drawLocal.draw.handlers.polygon.tooltip;
    customTooltips = formatTooltips(options.tooltipStrings);

    $(dom.drawArea).on('click', modes.activateDrawAreaMode);
    $(dom.cancel).on('click', cancelDraw);
}

function activate() {
    locationSearchUI.showDrawAreaControls();
    setTooltips(customTooltips);
    drawer.enable();
    map.on('draw:created', onDrawComplete);
    $(document).on('keydown', onKeyDown);
    polygonComplete = false;
}

function onDrawComplete(e) {
    locationSearchUI.completePolygon(e.layer);
    polygonComplete = true;
    modes.activateBrowseTreesMode(true);
}

function onKeyDown(e) {
    if (e.keyCode === 27) {  // Escape key
        cancelDraw();
    }
}

function cancelDraw() {
    modes.activateBrowseTreesMode();
}

function deactivate() {
    setTooltips(originalTooltips);
    drawer.disable();
    map.off('draw:created', onDrawComplete);
    $(document).off('keydown', onKeyDown);
    if (polygonComplete) {
        locationSearchUI.showCustomAreaControls();
    } else {
        locationSearchUI.showStandardControls();
    }
}

function formatTooltips(strings) {
    return {
        start: format(strings.start.message, strings.start.kicker),
        cont: format(strings.cont.message, strings.cont.kicker),
        end: format(strings.end.message, strings.end.kicker)
    };

    function format(message, kicker) {
        if (kicker) {
            message += '<br/><i>' + kicker + '</i>';
        }
        return message;
    }
}

function setTooltips(tooltips) {
    L.drawLocal.draw.handlers.polygon.tooltip = tooltips;
}

module.exports = {
    name: 'drawArea',
    init: init,
    activate: activate,
    deactivate: deactivate
};
