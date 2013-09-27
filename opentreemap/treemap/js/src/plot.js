"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    otmTypeahead = require('./otmTypeahead'),
    inlineEditForm = require('./inlineEditForm'),
    mapManager = require('./mapManager'),
    BU = require('BaconUtils'),
    plotMover = require('./plotMover'),
    plotMarker = require('./plotMarker'),
    csrf = require('./csrf'),
    imageUploadPanel = require('./imageUploadPanel'),
    streetView = require('./streetView'),
    diameterCalculator = require('./diameterCalculator');

exports.init = function(options) {
    // Set up cross-site forgery protection
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    _.each(options.typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });

    var udfRowTemplate = _.template(
        '<tr data-value-id="">' +
            '<% _.each(fields, function (field) { %>' +
            '<td> <%= field %> </td>' +
            '<% }) %>' +
            '</tr>');

    // Wire up collection udfs
    $('a[data-udf-id]').click(function() {
        var id = $(this).data('udf-id');
        var fields = $('table[data-udf-id="' + id + '"] * [data-field-name]').toArray();

        var data = _.map(fields, function(field) { return $(field).val(); });

        $(this).closest('table').append(udfRowTemplate({
            fields: data
        }));
    });

    imageUploadPanel.init(options.imageUploadPanel);

    var form = inlineEditForm.init(
            _.extend(options.inlineEditForm,{ onSaveBefore: onSaveBefore }));

    mapManager.init({
        config: options.config,
        selector: '#map',
        center: options.plotLocation.location,
        zoom: mapManager.ZOOM_PLOT
    });

    plotMarker.init(mapManager.map);

    plotMover.init({
        mapManager: mapManager,
        plotMarker: plotMarker,
        inlineEditForm: form,
        editLocationButton: options.plotLocation.edit,
        cancelEditLocationButton: options.plotLocation.cancel,
        location: options.plotLocation.location
    });

    diameterCalculator.init();

    function onSaveBefore(data) {
        plotMover.onSaveBefore(data);
    }

    if (options.config.instance.basemap.type === 'google') {
        var $streetViewContainer = $(options.streetView);
        $streetViewContainer.show();
        var panorama = streetView.create({
            streetViewElem: $streetViewContainer[0],
            noStreetViewText: options.noStreetViewText,
            location: options.plotLocation.location
        });
        form.saveOkStream
            .map(function(value) {
                return value['plot.geom'];
            })
            .filter(BU.isDefined)
            .onValue(panorama.update);
    }
};
