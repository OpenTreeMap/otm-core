"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    L = require('leaflet'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),
    buttonEnabler = require('treemap/buttonEnabler');

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

    var clickedIdStream = map.utfEvents
        .filter(inMyMode)
        .map('.data.' + config.utfGrid.mapfeatureIdKey);


    var popupHtmlStream = BU.fetchFromIdStream(clickedIdStream,
                                               getPlotPopupContent);

    var accordionHtmlStream = BU.fetchFromIdStream(clickedIdStream,
                                                   getPlotAccordionContent,
                                                   '');


    var plotUrlStream = clickedIdStream
        .map(idToPlotDetailUrl);

    plotUrlStream.onValue($fullDetailsButton, 'attr', 'href');
    plotUrlStream.onValue(inlineEditForm.setUpdateUrl);

    // Leaflet needs both the content and a coordinate to
    // show a popup, so zip map clicks together with content
    // requested via ajax
    BU.leafletEventStream(map, 'click')
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
        });
    accordionHtmlStream.onValue(_.bind($buttonGroup.show, $buttonGroup));

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
        url: config.instance.url + 'features/' + id + '/popup',
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

        var isPlot = $(html).data('mapfeature-type') === 'Plot';

        var popup = L.popup(popupOptions)
            .setLatLng(latLon)
            .setContent(html);

        popup.isPlot = isPlot;

        return popup;

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

    plotMarker.useTreeIcon(popup.isPlot);

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

    buttonEnabler.run({ config: config });

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
        plotMarker.unbindPopup();
        map.closePopup(popup);
    }
}

module.exports = {
    name: 'browseTrees',
    init: init,
    deactivate: deactivate
};
