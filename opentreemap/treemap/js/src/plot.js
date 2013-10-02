"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    otmTypeahead = require('./otmTypeahead'),
    inlineEditForm = require('./inlineEditForm'),
    mapManager = require('./mapManager'),
    BU = require('BaconUtils'),
    Bacon = require('baconjs'),
    U = require('./utility'),
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

    $(options.inlineEditForm.edit)
        .asEventStream('click')
        .onValue(function() {
            // Don't allow editing if not logged in
            // instead - go to the login page
            if (!options.config.loggedIn) {
                window.location = options.config.loginUrl +
                    window.location.href + 'edit';
            }
        });

    var shouldBeInEditModeBus = new Bacon.Bus();
    var shouldBeInEditModeStream = shouldBeInEditModeBus.merge(
        $(window).asEventStream('popstate')
            .map(function() { return U.getLastUrlSegment() === 'edit'; }));

    var form = inlineEditForm.init(
            _.extend(options.inlineEditForm,
                     { onSaveBefore: onSaveBefore,
                       shouldBeInEditModeStream: shouldBeInEditModeStream }));

    var startInEditMode = options.startInEditMode;
    var firstEditEventFound = false;

    form.inEditModeProperty.onValue(function(inEditMode) {
        var hrefHasEdit = U.getLastUrlSegment() === 'edit';

        if (inEditMode && !hrefHasEdit) {
            U.pushState(U.appendSegmentToUrl('edit'));
        } else if (!inEditMode && hrefHasEdit) {
            // inEditModeProperty fires a bunch of startup events.
            // if we're starting in edit mode we want to ignore
            // all events until we hit the first 'transition' to normal
            // mode. When we hit that we swallow the event and then
            // let things go as normal.
            if (startInEditMode && !firstEditEventFound) {
                firstEditEventFound = true;
            } else {
                U.pushState(U.removeLastUrlSegment());
            }
        }
    });

    if (startInEditMode) {
        if (options.config.loggedIn) {
            shouldBeInEditModeBus.push(true);
        } else {
            window.location = options.config.loginUrl + window.location.href;
        }
    }

    mapManager.init({
        config: options.config,
        selector: '#map',
        center: options.plotLocation.location,
        zoom: mapManager.ZOOM_PLOT
    });

    plotMarker.init(options.config, mapManager.map);

    plotMover.init({
        mapManager: mapManager,
        plotMarker: plotMarker,
        inlineEditForm: form,
        editLocationButton: options.plotLocation.edit,
        cancelEditLocationButton: options.plotLocation.cancel,
        location: options.plotLocation.location
    });

    diameterCalculator.init({ cancelStream: form.cancelStream,
                              saveOkStream: form.saveOkStream });

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
