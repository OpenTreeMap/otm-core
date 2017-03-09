"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    reverse = require('reverse'),
    config              = require('treemap/lib/config.js'),
    BU = require('treemap/lib/baconUtils.js'),
    boundarySelect = require('treemap/lib/boundarySelect');

var dom = {
    locationValue: '#boundary',
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
    polygon,
    locationChangeBus,
    createAnonymousBoundary = BU.jsonRequest('POST', reverse.anonymous_boundary());

function init(options) {
    locationChangeBus = new Bacon.Bus();
    map = options.map;
    $(dom.locationInput).on('input', showAppropriateWellButton);
    $(dom.clearLocationInput).click(clearLocationInput);
    $(dom.clearCustomArea).click(clearCustomArea);

    // Take away plugability from the outside world
    return locationChangeBus.map(_.identity);
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

function onSearchChanged(searchEvent) {
    var text = $(dom.locationInput).val(),
        boundaryId = (!!searchEvent && !!searchEvent.filter &&
                      !!searchEvent.filter &&
                      !!searchEvent.filter['mapFeature.geom'] &&
                      searchEvent.filter['mapFeature.geom'].IN_BOUNDARY) ||
                      null;
    if (text) {
        $(dom.locationSearched).html(text);
        showControls(dom.controls.searched);
    } else if (boundaryId !== null) {
        $(dom.locationValue).val(String(boundaryId));
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
        ring = lngLats.concat([_.take(lngLats)]),
        data = {polygon: ring},
        anonymousBoundaryStream = createAnonymousBoundary(data)
            .map(function (result) {
                return result.id;
            });

    setPolygon(newPolygon);
    anonymousBoundaryStream.onValue(function (boundaryID) {
        $(dom.locationValue).val(boundaryID);
        boundarySelect.shouldZoomOnLayerChange(false);
    });

    // Map id from anonymousBoundaryStream into the data structure
    // that locationChangeBus expects.
    var builtSearchStream = Bacon.combineTemplate({
        display: null,
        filter: {
            'mapFeature.geom': {IN_BOUNDARY: anonymousBoundaryStream}
        }
    });
    locationChangeBus.plug(builtSearchStream);
    return builtSearchStream;
}

function clearCustomArea(e) {
    showControls(dom.controls.standard);
    boundarySelect.shouldZoomOnLayerChange(true);
    $(dom.locationValue).val('');

    if (!!e) {
        locationChangeBus.push({
            display: null,
            filter: {}
        });
    }
}

function showControls(controls) {
    _.each(dom.controls, function (c) {
        $(c).hide();
    });
    $(controls).show();
}

function setParsedStream(parsed) {
    parsed.onValue(function () {
        if (polygon) {
            map.removeLayer(polygon);
            polygon = null;
        }
    });
}

module.exports = {
    init: init,
    getPolygon: getPolygon,
    setPolygon: setPolygon,
    completePolygon: completePolygon,
    onSearchChanged: onSearchChanged,
    showStandardControls: _.partial(showControls, dom.controls.standard),
    showDrawAreaControls: _.partial(showControls, dom.controls.drawArea),
    showCustomAreaControls: _.partial(showControls, dom.controls.customArea),
    showEditAreaControls: _.partial(showControls, dom.controls.editArea),
    clearCustomArea: clearCustomArea,
    setParsedStream: setParsedStream
};
