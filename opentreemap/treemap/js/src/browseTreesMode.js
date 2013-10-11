"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    L = require('leaflet'),
    Bacon = require('baconjs'),
    BU = require('BaconUtils');

var config,  // Module-level config set in `init` and read by helper functions
    map,
    popup,  // Most recent popup (so it can be deleted)
    plotMarker,
    $fullDetailsButton;

function idToPlotDetailUrl(id) {
    if (id) {
        return config.instance.url + 'plots/' + id + '/';
    } else {
        return '';
    }
}

function init(options) {
    config = options.config;
    map = options.map;
    plotMarker = options.plotMarker;
    $fullDetailsButton = options.$fullDetailsButton;

    var inMyMode = options.inMyMode, // function telling if my mode is active
        inlineEditForm = options.inlineEditForm,
        $accordionSection = options.$treeDetailAccordionSection;

    var clickedIdStream = map.utfEvents
        .filter(inMyMode)
        .map('.data.' + config.utfGrid.plotIdKey);

    var popupHtmlStream = BU.fetchFromIdStream(clickedIdStream,
                                               getPlotPopupContent);

    var accordionHtmlStream = BU.fetchFromIdStream(clickedIdStream,
                                                   getPlotAccordionContent,
                                                   '');


    var plotUrlStream = clickedIdStream
        .map(idToPlotDetailUrl);

    plotUrlStream.onValue($fullDetailsButton, 'attr', 'href');
    plotUrlStream.onValue(inlineEditForm.updateUrl);

    // Leaflet needs both the content and a coordinate to
    // show a popup, so zip map clicks together with content
    // requested via ajax
    BU.wrapOnEvent(map, 'click')
       .filter(inMyMode)
       .map('.latlng')
       .zip(popupHtmlStream, makePopup) // TODO: size is not being sent to makePopup
       .onValue(showPlotDetailPopup);

    accordionHtmlStream.onValue(function (html) {
        var visible = html !== '' && html !== undefined;

        $accordionSection.collapse(visible ? 'show' : 'hide');
    });
    accordionHtmlStream.onValue(function (html) {
            $('#plot-accordion').html(html);
            inlineEditForm.enableOrDisableEditButton();
        });

    var showTreeDetailLink = $accordionSection.parent().find('a');
    showTreeDetailLink.on('click', function(event) {
        if ($('#plot-accordion').html().length === 0) {
            event.stopPropagation();
        }
    });

    // Need to manually wire this here or we wont get the accordion effect
    $accordionSection.collapse({
        parent: $('#map-info'),
        toggle: false
    });

    $accordionSection.collapse('hide');
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
    size = size || {};
    if (latLon && html) {
        var popupOptions = {
            maxWidth: size.width || 320,
            maxHeight: size.height || 130
        };

        return L.popup(popupOptions)
            .setLatLng(latLon)
            .setContent(html);

        //TODO: Pan map if out of view
    } else {
        return null;
    }
}

function showPlotDetailPopup(newPopup) {
    if (popup) {
        map.closePopup(popup);
    }

    popup = newPopup;

    if (popup) {
        // Add the popup
        map.openPopup(popup);

        // Move the plot marker to this location
        plotMarker.place(popup._latlng);
        plotMarker.bindPopup(popup);

    } else {
        plotMarker.unbindPopup();
        plotMarker.hide();
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

function deactivate() {
    if (popup) {
        map.closePopup(popup);
    }
}

module.exports = {
    init: init,
    deactivate: deactivate
};
