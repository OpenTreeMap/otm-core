"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    OL = require('OpenLayers'),
    Bacon = require('baconjs'),
    fetchFromIdStream = require('./baconUtils').fetchFromIdStream;

// This module augments the OpenLayers global so we don't need `var thing =`
require('./openLayersUtfGridEventStream');

var config,
    map,
    inMyMode,               // function telling if my mode is active
    $sidebar;

function init(options) {
    config = options.config;
    map = options.map;
    inMyMode = options.inMyMode;
    $sidebar = options.$sidebar;
    
    var $accordionSection = $sidebar.find("#treeDetails");
    var utfGridMoveControl = new OL.Control.UTFGrid();

    utfGridMoveControl
        .asEventStream('move')
        .filter(inMyMode)
        .map(function (o) { return JSON.stringify(o || {}); })
        .assign($('#attrs'), 'html');

    // The control must be added to the map after setting up the
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

    // The control must be added to the map after setting up the
    // event streams
    map.addControl(utfGridClickControl);

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
    var clickedLatLonStream =
        map.asEventStream('click')
            .filter(inMyMode)
            .map(function (e) {
                return map.getLonLatFromPixel(e.xy);
            });

    clickedLatLonStream
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
        url: '/' + config.instance.id + '/plots/' + id + '/popup',
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
        url: '/' + config.instance.id + '/plots/' + id + '/detail',
        type: 'GET',
        dataType: 'html'
    });
    return Bacon.fromPromise(search);
}

module.exports = { init: init };
