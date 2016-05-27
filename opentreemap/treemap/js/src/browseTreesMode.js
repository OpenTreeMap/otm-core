"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),
    buttonEnabler = require('treemap/buttonEnabler'),
    format = require('util').format;

var config,  // Module-level config set in `init` and read by helper functions
    map,
    popup,  // Most recent popup (so it can be deleted)
    plotMarker,
    $fullDetailsButton;

function idToPlotDetailUrl(id) {
    if (id) {
        return config.instance.url + 'features/' + id + '/';
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
        $accordionSection = options.$treeDetailAccordionSection,
        $buttonGroup = options.$buttonGroup;

    var utfEventStream = map.utfEvents.filter(inMyMode),
        popupHtmlStream = utfEventStream.flatMap(getPopupContent),
        clickedIdStream = utfEventStream.map('.data.' + config.utfGrid.mapfeatureIdKey),
        accordionHtmlStream = BU.fetchFromIdStream(clickedIdStream,
                                                   getPlotAccordionContent,
                                                   ''),
        plotUrlStream = clickedIdStream.map(idToPlotDetailUrl);

    plotUrlStream.onValue($fullDetailsButton, 'attr', 'href');
    plotUrlStream.onValue(inlineEditForm.setUpdateUrl);

    // Leaflet needs both the content and a coordinate to
    // show a popup, so zip map clicks together with content
    // requested via ajax
    utfEventStream
       .map('.latlng')
       .zip(popupHtmlStream, makePopup)
       .onValue(showPopup);

    accordionHtmlStream.onValue(function () { $buttonGroup.show(); });

    accordionHtmlStream.assign($('#map-feature-accordion'), 'html');

    accordionHtmlStream
        .map(BU.isDefinedNonEmpty)
        .decode({true: 'show', false: 'hide'})
        .onValue(_.bind($accordionSection.collapse, $accordionSection));

    var featureTypeStream = accordionHtmlStream.map($)
            .map('.attr', 'data-map-feature-type');

    featureTypeStream
        .decode({plot: 'visible', resource: 'hidden'})
        .assign($('#quick-edit-button'), 'css', 'visibility');

    featureTypeStream
        .decode({plot: config.trans.treeDetails,
                 resource: config.trans.resourceDetails})
        .assign($('#accordion-map-feature-detail-tab'), 'html');

    var showTreeDetailLink = $accordionSection.parent().find('a');
    showTreeDetailLink.on('click', function(event) {
        if ($('#map-feature-accordion').html().length === 0) {
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

function getPopupContent(utfGridEvent) {
    var data = utfGridEvent.data,
        featureId = data ? data[config.utfGrid.mapfeatureIdKey] : null;

    if (featureId) {
        return getPopup(config.instance.url + 'features/' + featureId + '/popup');

    } else if (config.instance.canopyEnabled) {
        var latlng = utfGridEvent.latlng;
        return getPopup(config.instance.canopyForPointUrl +
            format('?lng=%d&lat=%d', latlng.lng, latlng.lat));

    } else {
        return null;
    }

    function getPopup(url) {
        return Bacon.fromPromise($.ajax({
            url: url,
            type: 'GET',
            dataType: 'html'
        }));
    }
}

function makePopup(latLon, html) {
    if (latLon && html) {
        var popupOptions = {
            maxWidth: 400,
            maxHeight: 300
        };

        var popup = L.popup(popupOptions)
            .setLatLng(latLon)
            .setContent(html);
        
        var mapFeatureType = $(html).data('mapfeature-type');
        popup.isMapFeature = mapFeatureType !== undefined;
        popup.isPlot = mapFeatureType === 'Plot';

        return popup;
    } else {
        return null;
    }
}

function showPopup(newPopup) {
    if (popup) {
        map.closePopup(popup);
    }

    popup = newPopup;

    plotMarker.useTreeIcon(popup ? popup.isPlot : false);

    if (popup) {
        map.openPopup(popup);
    }

    if (popup && popup.isMapFeature) {
        // Move the plot marker to this location
        plotMarker.place(popup._latlng);
        plotMarker.bindPopup(popup);
    } else {
        plotMarker.unbindPopup();
        plotMarker.hide();
    }

    buttonEnabler.run({ config: config });
}

function getPlotAccordionContent(id) {
    var search = $.ajax({
        url: config.instance.url + 'features/' + id + '/detail',
        type: 'GET',
        dataType: 'html'
    });
    return Bacon.fromPromise(search);
}

function deactivate() {
    if (popup) {
        plotMarker.unbindPopup();
        map.closePopup(popup);
    }
}

module.exports = {
    name: 'browseTrees',
    init: init,
    deactivate: deactivate
};
