"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    inlineEditForm = require('treemap/inlineEditForm'),
    MapManager = require('treemap/MapManager'),
    BU = require('treemap/baconUtils'),
    Bacon = require('baconjs'),
    U = require('treemap/utility'),
    plotMover = require('treemap/plotMover'),
    plotDelete = require('treemap/plotDelete'),
    plotMarker = require('treemap/plotMarker'),
    statePrompter = require('treemap/statePrompter'),
    csrf = require('treemap/csrf'),
    imageUploadPanel = require('treemap/imageUploadPanel'),
    reverseGeocodeStreamAndUpdateAddressesOnForm =
        require('treemap/reverseGeocodeStreamAndUpdateAddressesOnForm'),
    streetView = require('treemap/streetView'),
    History = require('history'),
    alerts = require('treemap/alerts');

exports.init = function(options) {
    var $ecoBenefits = $(options.ecoBenefits),
        detailUrl = window.location.href;

    if (U.getLastUrlSegment(detailUrl) == 'edit') {
        detailUrl = U.removeLastUrlSegment(detailUrl);
    }

    // Set up cross-site forgery protection
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    var prompter = statePrompter.init({
        warning: options.config.trans.exitWarning,
        question: options.config.trans.exitQuestion
    });

    // Add threaded comments "reply" links
    var commentFormTempl = $("#template-comment").html();

    $('a[data-comment-id]').click(function () {
        var $a = $(this);

        // Close other forms
        $(".comment-reply-form").remove();

        var templ = $("#template-comment").html();
        $a.closest(".comment").append(_.template(commentFormTempl, {
            parent: $a.data("comment-id"),
            classname: 'comment-reply-form'
        }));
    });

    if (options.config.loggedIn) {
        $('#comments-container').append(_.template(commentFormTempl, {
            parent: '',
            classname: 'comment-create-form'
        }));
    }

    var imageFinishedStream = imageUploadPanel.init(options.imageUploadPanel);

    var shouldBeInEditModeBus = new Bacon.Bus();
    var shouldBeInEditModeStream = shouldBeInEditModeBus.merge(
        $(window).asEventStream('popstate')
            .map(function() { return U.getLastUrlSegment() === 'edit'; }));

    var form = inlineEditForm.init(
            _.extend(options.inlineEditForm,
                     { config: options.config,
                       updateUrl: detailUrl,
                       onSaveBefore: onSaveBefore,
                       shouldBeInEditModeStream: shouldBeInEditModeStream,
                       errorCallback: alerts.makeErrorCallback(options.config)
                     }));

    var deleter = plotDelete.init({
        config: options.config,
        delete: options.delete,
        deleteConfirm: options.deleteConfirm,
        deleteCancel: options.deleteCancel,
        deleteConfirmationBox: options.deleteConfirmationBox,
        treeIdColumn: options.treeIdColumn
    });

    if (options.config.instance.supportsEcobenefits) {
        var updateEcoUrl = U.appendSegmentToUrl('eco', detailUrl);
        form.saveOkStream
            .map($ecoBenefits)
            .onValue('.load', updateEcoUrl);
    }

    var sidebarUpdate = form.saveOkStream.merge(imageFinishedStream),
        updateSidebarUrl = U.appendSegmentToUrl('sidebar', detailUrl);
    sidebarUpdate
        .map($(options.sidebar))
        .onValue('.load', updateSidebarUrl);

    form.inEditModeProperty.onValue(function(inEditMode) {
        var hrefHasEdit = U.getLastUrlSegment() === 'edit';

        if (inEditMode) {
            prompter.lock();
            if (!hrefHasEdit) {
                History.replaceState(null, document.title, U.appendSegmentToUrl('edit'));
            }
        } else {
            prompter.unlock();
            if (hrefHasEdit) {
                History.replaceState(null, document.title, U.removeLastUrlSegment());
            }
        }
    });

    if (options.startInEditMode) {
        if (options.config.loggedIn) {
            shouldBeInEditModeBus.push(true);
        } else {
            window.location = options.config.loginUrl + window.location.href;
        }
    }

    var mapManager = new MapManager();
    mapManager.createTreeMap({
        config: options.config,
        selector: '#map',
        disableScrollWithMouseWheel: true,
        center: options.location.point,
        zoom: mapManager.ZOOM_PLOT
    });

    plotMarker.init(options.config, mapManager.map);
    plotMarker.useTreeIcon(options.useTreeIcon);

    reverseGeocodeStreamAndUpdateAddressesOnForm(
        options.config, plotMarker.moveStream, options.form);

    var currentPlotMover = plotMover.init({
        mapManager: mapManager,
        plotMarker: plotMarker,
        inlineEditForm: form,
        editLocationButton: options.location.edit,
        cancelEditLocationButton: options.location.cancel,
        location: options.location.point
    });

    var detailUrlPrefix = U.removeLastUrlSegment(detailUrl),
        clickedIdStream = mapManager.map.utfEvents
            .map('.data.' + options.config.utfGrid.mapfeatureIdKey)
            .filter(BU.isDefinedNonEmpty);

    clickedIdStream
        .filter(BU.not, options.featureId)
        .map(_.partialRight(U.appendSegmentToUrl, detailUrlPrefix, false))
        .onValue(_.bind(window.location.assign, window.location));

    function onSaveBefore(data) {
        currentPlotMover.onSaveBefore(data);
    }

    if (options.config.instance.basemap.type === 'google') {
        var $streetViewContainer = $(options.streetView);
        $streetViewContainer.show();
        var panorama = streetView.create({
            streetViewElem: $streetViewContainer[0],
            noStreetViewText: options.config.trans.noStreetViewText,
            location: options.location.point
        });
        form.saveOkStream
            .map('.formData')
            .map(BU.getValueForKey, 'plot.geom')
            .filter(BU.isDefined)
            .onValue(panorama.update);
    }

    return {
        inlineEditForm: form
    };
};
