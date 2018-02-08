"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    reverse = require('reverse'),
    config = require('treemap/lib/config.js'),
    BU = require('treemap/lib/baconUtils.js'),
    boundarySelect = require('treemap/lib/boundarySelect');

var dom = {
    boundaryIdForSearch: '#boundary',
    locationInput: '#boundary-typeahead',
    drawArea: '.draw-area',
    clearLocationInput: '.clear-location-input',
    clearCustomArea: '.clear-custom-area',
    controls: {
        standard: '#location-search-well',
        drawArea: '#draw-area-controls',
        customArea: '#custom-area-controls',
        editArea: '#edit-area-controls'
    }
};

var map,
    polygon,
    customAreaSearchBus,
    createAnonymousBoundary = BU.jsonRequest('POST', reverse.anonymous_boundary());

function init(options) {
    var mapManager = options.mapManager;
    mapManager.customizeVertexIcons();
    customAreaSearchBus = new Bacon.Bus();
    map = mapManager.map;
    $(dom.locationInput).on('input', showAppropriateWellButton);
    $(dom.clearLocationInput).on('click', clearLocationInput);
    $(dom.clearCustomArea).on('click', clearCustomArea);

    return customAreaSearchBus.map(_.identity);
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
    var boundaryId = parseInt($(dom.boundaryIdForSearch).val(), 10),
        hasBoundary = _.isNumber(boundaryId) && !_.isNaN(boundaryId),
        searchedText = $(dom.locationInput).val();

    if (hasBoundary && !searchedText) {
        showControls(dom.controls.customArea);
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

function completePolygon(newPolygon) {
    var lngLats = _.map(newPolygon.getLatLngs()[0], function (p) {
            return [p.lng, p.lat];
        }),
        ring = lngLats.concat(_.take(lngLats)),
        data = {polygon: ring},
        anonymousBoundaryStream = createAnonymousBoundary(data)
            .map(function (result) {
                return result.id;
            });

    setPolygon(newPolygon);
    var identifiedBoundaryStream = anonymousBoundaryStream
        .doAction(function (boundaryID) {
            $(dom.boundaryIdForSearch).val(boundaryID);
            boundarySelect.shouldZoomOnLayerChange(false);
        });

    // `customAreaSearchBus` prompts `searchBar` to call `Search.buildSearch`,
    // which rebuilds the search string from scratch.
    //
    // That must happen after an anonymous boundary has been created,
    // and its id set in `dom.boundaryIdForSearch`,
    // which supplies the value to `Search.buildSearch`.
    customAreaSearchBus.plug(identifiedBoundaryStream);
}

function clearCustomArea(e) {
    showControls(dom.controls.standard);
    boundarySelect.shouldZoomOnLayerChange(true);
    $(dom.boundaryIdForSearch).val('');

    // The existence of an argument tells us that this method was invoked
    // from jQuery user event, as opposed to the url being set.
    if (!!e) {
        customAreaSearchBus.push();
    }
}

function showControls(controls) {
    _.each(dom.controls, function (c) {
        $(c).hide();
    });
    $(controls).show();
}

function removeDrawingLayer() {
    if (polygon) {
        map.removeLayer(polygon);
        polygon = null;
    }
}

module.exports = {
    init: init,
    getPolygon: getPolygon,
    setPolygon: setPolygon,
    completePolygon: completePolygon,
    removeDrawingLayer: removeDrawingLayer,
    onSearchChanged: onSearchChanged,
    showStandardControls: _.partial(showControls, dom.controls.standard),
    showDrawAreaControls: _.partial(showControls, dom.controls.drawArea),
    showCustomAreaControls: _.partial(showControls, dom.controls.customArea),
    showEditAreaControls: _.partial(showControls, dom.controls.editArea),
    clearCustomArea: clearCustomArea,
    showAppropriateWellButton: showAppropriateWellButton
};
