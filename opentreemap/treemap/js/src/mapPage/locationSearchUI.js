"use strict";

var $ = require('jquery'),
    _ = require('lodash');

var dom = {
    locationInput: '#boundary-typeahead',
    locationSearched: '#location-searched .text',
    drawArea: '.draw-area',
    clearLocationInput: '.clear-location-input',
    clearCustomArea: '.clear-custom-area',
    controls: {
        standard: '#location-search-well',
        searched: '#location-searched',
        drawArea: '#draw-area-controls',
        customArea: '#custom-area-controls',
        editArea: '#edit-area-controls'
    }
};

var map,
    polygon;

function init(options) {
    map = options.map;
    $(dom.locationInput).on('input', showAppropriateWellButton);
    $(dom.clearLocationInput).click(clearLocationInput);
    $(dom.clearCustomArea).click(clearCustomArea);

    options.builtSearchEvents.onValue(onSearchChanged);
}

function showAppropriateWellButton() {
    var hasValue = ($(dom.locationInput).val().length > 0);
    $(dom.drawArea).toggle(!hasValue);
    $(dom.clearLocationInput).toggle(hasValue);
}

function clearLocationInput() {
    $(dom.locationInput).val('');
    showAppropriateWellButton();
}

function onSearchChanged() {
    var text = $(dom.locationInput).val();
    if (text) {
        showControls(dom.controls.searched);
        $(dom.locationSearched).html(text);
    } else {
        showControls(dom.controls.standard);
        showAppropriateWellButton();
    }
}

function getPolygon() {
    return polygon;
}

function setPolygon(newPolygon) {
    polygon = newPolygon.addTo(map);
}

function clearCustomArea() {
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
