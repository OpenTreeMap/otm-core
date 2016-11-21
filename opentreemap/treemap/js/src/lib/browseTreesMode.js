"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    Bacon = require('baconjs'),
    reverse = require('reverse'),
    BU = require('treemap/lib/baconUtils.js'),
    buttonEnabler = require('treemap/lib/buttonEnabler.js'),
    config = require('treemap/lib/config.js'),
    format = require('util').format;

var map,
    popup,  // Most recent popup (so it can be deleted)
    embed,  // True if embed is in the query string
    plotMarker,
    $fullDetailsButton;

function idToPlotDetailUrl(id) {
    if (id) {
        return reverse.map_feature_detail({
            instance_url_name: config.instance.url_name,
            feature_id: id
        });
    } else {
        return '';
    }
}

function init(options) {
    map = options.map;
    embed = options.embed;
    plotMarker = options.plotMarker;
    $fullDetailsButton = options.$fullDetailsButton;

    var inMyMode = options.inMyMode, // function telling if my mode is active
        inlineEditForm = options.inlineEditForm,
        $accordionSection = options.$treeDetailAccordionSection,
        $buttonGroup = options.$buttonGroup;

    var singleSearchResultAsMockUtfEventStream = options.completedSearchStream
            .map(getSingleSearchResultAsMockUtfEvent)
            .filter(BU.isDefinedNonEmpty),
        utfEventStream =
            Bacon.mergeAll(map.utfEvents, singleSearchResultAsMockUtfEventStream)
                .filter(inMyMode),

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
        .assign($('body'), 'toggleClass', 'feature-selected');

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
    if (embed) {
        showTreeDetailLink.filter('#full-details-button').attr('target', '_blank');
    }
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

function getSingleSearchResultAsMockUtfEvent(html) {
    var $result = $(html).filter('#single-result');
    if ($result.length == 1) {
        return {
            data: {
                id: $result.data('id')
            },
            latlng: {
                lat: $result.data('lat'),
                lng: $result.data('lon')
            }
        };
    } else {
        return undefined;
    }
}

function getPopupContent(utfGridEvent) {
    var data = utfGridEvent.data,
        featureId = data ? data[config.utfGrid.mapfeatureIdKey] : null;

    if (featureId) {
        return getPopup(reverse.map_feature_popup({
            instance_url_name: config.instance.url_name,
            feature_id: featureId
        }));

    } else if (config.instance.canopyEnabled) {
        var latlng = utfGridEvent.latlng;
        return getPopup(reverse.canopy_popup(config.instance.url_name) +
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

        var $popup = $(html);
        if (embed) {
            $popup.find('a').attr('target', '_blank');
        }

        var $popupContents = $($popup.html());
        $popupContents.data('latlon', latLon);

        var popup = L.popup(popupOptions)
            .setLatLng(latLon)
            .setContent($popupContents[0]);

        var mapFeatureType = $popup.data('mapfeature-type');
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

    buttonEnabler.run();
}

function getPlotAccordionContent(id) {
    var search = $.ajax({
        url: reverse.map_feature_accordion({
            instance_url_name: config.instance.url_name,
            feature_id: id
        }),
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
