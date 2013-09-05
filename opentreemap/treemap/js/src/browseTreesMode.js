"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    OL = require('OpenLayers'),
    Bacon = require('baconjs'),
    fetchFromIdStream = require('./baconUtils').fetchFromIdStream;

// These modules augment the OpenLayers global so we don't need `var thing =`
require('./openLayersUtfGridEventStream');
require('./openLayersMapEventStream');

var config,  // Module-level config set in `init` and read by helper functions
    map,
    popup;   // Most recent popup (so it can be deleted)

function init(options) {
    config = options.config;
    map = options.map;

    var inMyMode = options.inMyMode, // function telling if my mode is active
        inlineEditForm = options.inlineEditForm,
        $accordionSection = options.$treeDetailAccordionSection,
        utfGridMoveControl = new OL.Control.UTFGrid();

    utfGridMoveControl
        .asEventStream('move')
        .filter(inMyMode)
        .map(function (o) { return JSON.stringify(o || {}); })
        .assign($('#attrs'), 'html');

    // The utfGridMoveControl must be added to the map after setting up the
    // event stream
    map.addControl(utfGridMoveControl);

    var utfGridClickControl = new OL.Control.UTFGrid();

    var clickedIdStream = utfGridClickControl
        .asEventStream('click')
        .filter(inMyMode)
        .map('.' + config.utfGrid.plotIdKey);

    var popupHtmlStream = fetchFromIdStream(clickedIdStream, 
                                            getPlotPopupContent);

    var accordionHtmlStream = fetchFromIdStream(clickedIdStream, 
                                                getPlotAccordionContent, 
                                                '');

    clickedIdStream.onValue(function (id) {
        inlineEditForm.updateUrl = '/' + config.instance.id + '/plots/' + id;
    }
);

    // The utfGridClickControl must be added to the map after setting up the
    // event streams
    map.addControl(utfGridClickControl);

    // OpenLayers needs both the content and a coordinate to
    // show a popup, so zip map clicks together with content
    // requested via ajax
    map.asEventStream('click')
       .filter(inMyMode)
       .map(function (e) {
            return map.getLonLatFromPixel(e.xy);
        })
       .zip(popupHtmlStream, makePopup) // TODO: size is not being sent to makePopup
       .onValue(showPlotDetailPopup);

    accordionHtmlStream.onValue(function (html) {
        if (html !== '' && html !== undefined) {
            $('#plot-accordion').html(html);
            $accordionSection.removeClass('collapse');
        } else {
            $accordionSection.addClass('collapse'); 
        }
    });
}

function getPlotPopupContent(id) {
    var search = $.ajax({
        url: config.instance.url + 'plots/' + id + '/popup',
        type: 'GET',
        dataType: 'html'
    });
    return Bacon.fromPromise(search);
}

function makePopup(latLon, html, size) {
    if (latLon && html) {
        return new OL.Popup("plot-popup", latLon, size, html, true);
    } else {
        return null;
    }
}

function showPlotDetailPopup(newPopup) {
    if (popup) {
        map.removePopup(popup);
    }
    if (newPopup) {
        map.addPopup(newPopup);
    }
    popup = newPopup;
};

function getPlotAccordionContent(id) {
    var search = $.ajax({
        url: config.instance.url + 'plots/' + id + '/detail',
        type: 'GET',
        dataType: 'html'
    });
    return Bacon.fromPromise(search);
}

function deactivate() {
    if (popup) {
        map.removePopup(popup);
    }
};

module.exports = {
    init: init,
    //activate: activate,
    deactivate: deactivate
};
