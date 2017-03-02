"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet');

var dom = {
    clearLocationSearch: '.clear-location-search',
    controls: {
        standard: '#location-search-well',
        drawArea: '#draw-area-controls',
        customArea: '#custom-area-controls',
        editArea: '#edit-area-controls'
    }
};

var map,
    polygon;

function init(options) {
    map = options.map;
    $(dom.clearLocationSearch).click(clearLocationSearch);
}

function getPolygon() {
    return polygon;
}

function setPolygon(newPolygon) {
    polygon = newPolygon.addTo(map);
}

function clearLocationSearch() {
    if (polygon) {
        map.removeLayer(polygon);
        polygon = null;
    }
    showControls(dom.controls.standard);
}

function showControls(controls) {
    _.each(dom.controls, function (c) {
        $(c).hide();
    });
    $(controls).show();
}

module.exports = {
    init: init,
    getPolygon: getPolygon,
    setPolygon: setPolygon,
    showStandardControls: _.partial(showControls, dom.controls.standard),
    showDrawAreaControls: _.partial(showControls, dom.controls.drawArea),
    showCustomAreaControls: _.partial(showControls, dom.controls.customArea),
    showEditAreaControls: _.partial(showControls, dom.controls.editArea)
};
