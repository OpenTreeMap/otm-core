"use strict";

var L = require('leaflet'),
    adHocPolygon = require('treemap/mapPage/adHocPolygon.js'),
    plotMarker   = require('treemap/lib/plotMarker.js');

var map,
    drawer,
    originalTooltips,
    customTooltips;

function init(options) {
    map = options.map;
    drawer = new L.Draw.Polygon(map);
    originalTooltips = L.drawLocal.draw.handlers.polygon.tooltip;
    customTooltips = formatTooltips(options.tooltipStrings);
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

function activate() {
    plotMarker.hide();
    setTooltips(customTooltips);
    drawer.enable();
    map.on('draw:created', function (e) {
        adHocPolygon.onNewPolygon(e.layer);
    });
    adHocPolygon.onActivate();
}

function deactivate() {
    setTooltips(originalTooltips);
    drawer.disable();
    map.off('draw:created');
    adHocPolygon.onDeactivate();
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
