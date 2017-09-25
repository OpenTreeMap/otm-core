"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    Bacon = require('baconjs'),
    reverse = require('reverse'),
    BU = require('treemap/lib/baconUtils.js'),
    buttonEnabler = require('treemap/lib/buttonEnabler.js'),
    config = require('treemap/lib/config.js'),
    format = require('util').format,
    plotMarker = require('treemap/lib/plotMarker.js'),
    webMercatorToLeafletLatLng = require('treemap/lib/utility').webMercatorToLeafletLatLng;

var dom = {
        sidebarContent: '#map-info',
        mapFeatureAccordion: '#map-feature-accordion',
        treeDetailAccordion: '#tree-detail',
        fullDetailsButton: '#full-details-button',
        quickEditButton: '#quick-edit-button',
        popupSections: '#map-feature-popup .popup-content',
        popupPagingButtons: '#map-feature-popup .popup-paging .btn'
    },

    map,
    popup,  // Most recent popup (so it can be deleted)
    embed;  // True if embed is in the query string

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

    var inMyMode = options.inMyMode, // function telling if my mode is active
        inlineEditForm = options.inlineEditForm;

    var singleSearchResultAsMockUtfEventStream = options.completedSearchStream
            .map(getSingleSearchResultAsMockUtfEvent)
            .filter(BU.isDefinedNonEmpty),
        utfEventStream =
            Bacon.mergeAll(map.utfEvents, singleSearchResultAsMockUtfEventStream)
                .filter(inMyMode),

        popupHtmlStream = utfEventStream.flatMap(getPopupContent),

        clickedIdStream = utfEventStream.map('.data.' + config.utfGrid.mapfeatureIdKey),
        pagingIdStream = $('body').asEventStream('click', dom.popupPagingButtons)
            .doAction(changePopupSelection)
            .doAction(toggleAccordion, '')
            .debounce(300)
            .map(getIdFromPopup),
        idStream = Bacon.mergeAll(clickedIdStream, pagingIdStream),

        accordionHtmlStream = BU.fetchFromIdStream(idStream,
                                                   getPlotAccordionContent,
                                                   ''),
        plotUrlStream = idStream.map(idToPlotDetailUrl);

    plotUrlStream.onValue($(dom.fullDetailsButton), 'attr', 'href');
    plotUrlStream.onValue(inlineEditForm.setUpdateUrl);

    // Leaflet needs both the content and a coordinate to
    // show a popup, so zip map clicks together with content
    // requested via ajax
    utfEventStream
       .map('.latlng')
       .zip(popupHtmlStream, makePopup)
       .onValue(togglePopup);

    accordionHtmlStream.onValue(toggleAccordion);

    var featureTypeStream = accordionHtmlStream.map($)
            .map('.attr', 'data-map-feature-type');

    featureTypeStream
        .decode({plot: 'visible', resource: 'hidden'})
        .assign($(dom.quickEditButton), 'css', 'visibility');

    var showTreeDetailLink = $(dom.treeDetailAccordion).parent().find('a');
    if (embed) {
        showTreeDetailLink.filter('#full-details-button').attr('target', '_blank');
    }
    showTreeDetailLink.on('click', function(event) {
        if ($(dom.mapFeatureAccordion).html().length === 0) {
            event.stopPropagation();
        }
    });

    // Need to manually wire this here or we wont get the accordion effect
    $(dom.treeDetailAccordion)
        .collapse({
            parent: $(dom.sidebarContent),
            toggle: false
        })
        .collapse('hide');
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

        var $popupContents = $($popup[0].outerHTML);
        $popupContents.data('latlon', latLon);

        var popup = L.popup(popupOptions)
            .setLatLng(latLon)
            .setContent($popupContents[0]);

        var mapFeatureType = $popup.find('[data-mapfeature-type]').data('mapfeature-type');
        popup.isMapFeature = mapFeatureType !== undefined;
        popup.isPlot = mapFeatureType === 'Plot';

        return popup;
    } else {
        return null;
    }
}

function togglePopup(newPopup) {
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
        // No popup, or popup without a marker (e.g. just canopy percent)
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

function toggleAccordion(html) {
    var shouldShow = !!html;
    $(dom.mapFeatureAccordion).html(html);
    $(dom.treeDetailAccordion).collapse(shouldShow ? 'show' : 'hide');
    $('body').toggleClass('feature-selected', shouldShow);  // for mobile
}

function deactivate(options) {
    if (popup) {
        plotMarker.unbindPopup();
        map.closePopup(popup);
    }
    var keepSelection = options && options.keepSelection;
    if (!keepSelection) {
        clearSelection();
    }
}

function clearSelection() {
    toggleAccordion(false);
    plotMarker.hide();
}

function changePopupSelection(e) {
    var $sections = $(dom.popupSections),
        $current = $sections.filter(':not(.hidden)'),
        $new = $(e.currentTarget).is('.next') ? $current.next() : $current.prev(),
        loc = webMercatorToLeafletLatLng($new.data('x'), $new.data('y'));

    $sections.addClass('hidden');
    $new.removeClass('hidden');

    plotMarker.useTreeIcon($new.data('mapfeature-type') === 'Plot');
    plotMarker.place(loc);
}

function getIdFromPopup(e) {
    return $(dom.popupSections).filter(':visible').data('feature-id');
}

module.exports = {
    name: 'browseTrees',
    init: init,
    deactivate: deactivate
};
