"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    OL = require('OpenLayers'),
    Bacon = require('baconjs'),
    fetchFromIdStream = require('./baconUtils').fetchFromIdStream;

// These modules augment the OpenLayers global so we don't need `var thing =`
require('./openLayersUtfGridEventStream');
require('./openLayersMapEventStream');

// Module-level config set in `init` and read by helper functions
var config;               

function init(options) {
    config = options.config;

    var map = options.map;
    var inMyMode = options.inMyMode; // function telling if my mode is active
    var $sidebar = options.$sidebar;
    var $accordionSection = options.$treeDetailAccordionSection;
    var utfGridMoveControl = new OL.Control.UTFGrid();

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

    // The utfGridClickControl must be added to the map after setting up the
    // event streams
    map.addControl(utfGridClickControl);

    // A closure is used here to keep a reference to any currently
    // displayed popup so it can be removed
    var showPlotDetailPopup = (function(map) {
        var existingPopup;
        return function(popup) {
            if (existingPopup) { map.removePopup(existingPopup); }
            if (popup) { map.addPopup(popup); }
            existingPopup = popup;
        };
    }(map));

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

    accordionHtmlStream.toProperty('').assign($('#plot-accordion'), "html");

    accordionHtmlStream.onValue(function (html) {
        if (html !== '' && html !== undefined) {
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

function getPlotAccordionContent(id) {
    var search = $.ajax({
        url: config.instance.url + 'plots/' + id + '/detail',
        type: 'GET',
        dataType: 'html'
    });
    return Bacon.fromPromise(search);
}

module.exports = { init: init };
