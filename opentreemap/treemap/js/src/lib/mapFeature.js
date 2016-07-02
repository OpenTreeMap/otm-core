"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    toastr = require('toastr'),
    inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    MapManager = require('treemap/lib/MapManager.js'),
    R = require('ramda'),
    BU = require('treemap/lib/baconUtils.js'),
    Bacon = require('baconjs'),
    U = require('treemap/lib/utility.js'),
    geometryMover = require('treemap/lib/geometryMover.js'),
    plotMarker = require('treemap/lib/plotMarker.js'),
    statePrompter = require('treemap/lib/statePrompter.js'),
    csrf = require('treemap/lib/csrf.js'),
    imageUploadPanel = require('treemap/lib/imageUploadPanel.js'),
    socialMediaSharing = require('treemap/lib/socialMediaSharing.js'),
    reverseGeocodeStreamAndUpdateAddressesOnForm =
        require('treemap/lib/reverseGeocodeStreamAndUpdateAddressesOnForm.js'),
    streetView = require('treemap/lib/streetView.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse'),
    alerts = require('treemap/lib/alerts.js'),
    comments = require('otm_comments/lib/comments.js'),

    dom = {
        favoriteLink: '#favorite-link',
        favoriteIcon: '#favorite-star',
        ecoBenefits: '#ecobenefits',
        sidebar: '#sidebar',
        form: '#map-feature-form',
        streetView: '#street-view',
        location: {
            edit: '#edit-location',
            cancel: '#cancel-edit-location',
        },
    };

exports.init = function() {
    var $ecoBenefits = $(dom.ecoBenefits),
        detailUrl = window.location.href;

    if (U.getLastUrlSegment(detailUrl) == 'edit') {
        detailUrl = U.removeLastUrlSegment(detailUrl);
    }

    comments('#comments-container');

    // Set up cross-site forgery protection
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    var prompter = statePrompter.init({
        warning: config.trans.exitWarning,
        question: config.trans.exitQuestion
    });

    var imageFinishedStream = imageUploadPanel.init({
        panelId: '#add-photo-modal',
        dataType: 'html',
        imageContainer: '#photo-carousel',
        lightbox: '#photo-lightbox',
    });

    var shouldBeInEditModeBus = new Bacon.Bus();
    var shouldBeInEditModeStream = shouldBeInEditModeBus.merge(
        $(window).asEventStream('popstate')
            .map(function() { return U.getLastUrlSegment() === 'edit'; }));

    var currentMover;

    var form = inlineEditForm.init({
        form: dom.form,
        edit: '#edit-map-feature',
        save: '#save-edit-map-feature',
        cancel: '#cancel-edit-map-feature',
        displayFields: '[data-class="display"]',
        editFields: '[data-class="edit"]',
        validationFields: '[data-class="error"]',
        updateUrl: detailUrl,
        shouldBeInEditModeStream: shouldBeInEditModeStream,
        errorCallback: alerts.errorCallback,
        onSaveBefore: function (data) { currentMover.onSaveBefore(data); },
        onSaveAfter: function (data) { currentMover.onSaveAfter(data); }
    });

    if (config.instance.supportsEcobenefits) {
        var updateEcoUrl = reverse.plot_eco({
            instance_url_name: config.instance.url_name,
            feature_id: window.mapFeature.featureId
        });
        form.saveOkStream
            .map($ecoBenefits)
            .onValue('.load', updateEcoUrl);
    }

    var sidebarUpdate = form.saveOkStream.merge(imageFinishedStream),
        updateSidebarUrl = U.appendSegmentToUrl('sidebar', detailUrl);
    sidebarUpdate
        .map($(dom.sidebar))
        .onValue('.load', updateSidebarUrl);

    form.inEditModeProperty.onValue(function(inEditMode) {
        var hrefHasEdit = U.getLastUrlSegment() === 'edit';

        if (inEditMode) {
            prompter.lock();
            if (!hrefHasEdit) {
                history.replaceState(null, document.title, U.appendSegmentToUrl('edit'));
            }
        } else {
            prompter.unlock();
            if (hrefHasEdit) {
                history.replaceState(null, document.title, U.removeLastUrlSegment());
            }
        }
    });

    if (window.mapFeature.startInEditMode) {
        if (config.loggedIn) {
            shouldBeInEditModeBus.push(true);
        } else {
            window.location = config.loginUrl + window.location.href;
        }
    }

    var mapManager = new MapManager();
    mapManager.createTreeMap({
        domId: 'map',
        disableScrollWithMouseWheel: true,
        centerWM: window.mapFeature.location.point,
        zoom: mapManager.ZOOM_PLOT
    });

    var moverOptions = {
        mapManager: mapManager,
        inlineEditForm: form,
        editLocationButton: dom.location.edit,
        cancelEditLocationButton: dom.location.cancel,
        resourceType: window.mapFeature.resourceType,
        location: window.mapFeature.location
    };

    if (window.mapFeature.isEditablePolygon) {
        currentMover = geometryMover.polygonMover(moverOptions);
    } else {
        plotMarker.init(mapManager.map);
        plotMarker.useTreeIcon(window.mapFeature.useTreeIcon);
        reverseGeocodeStreamAndUpdateAddressesOnForm(plotMarker.moveStream, dom.form);
        moverOptions.plotMarker = plotMarker;
        currentMover = geometryMover.plotMover(moverOptions);
    }

    var detailUrlPrefix = U.removeLastUrlSegment(detailUrl),
        clickedIdStream = mapManager.map.utfEvents
            .map('.data.' + config.utfGrid.mapfeatureIdKey)
            .filter(BU.isDefinedNonEmpty);

    clickedIdStream
        .filter(BU.not, window.mapFeature.featureId)
        .map(_.partialRight(U.appendSegmentToUrl, detailUrlPrefix, false))
        .filter(R.not(currentMover.isEnabled))
        .onValue(_.bind(window.location.assign, window.location));

    if (config.instance.basemap.type === 'google') {
        var $streetViewContainer = $(dom.streetView);
        $streetViewContainer.show();
        var panorama = streetView.create({
            streetViewElem: $streetViewContainer[0],
            noStreetViewText: config.trans.noStreetViewText,
            location: window.mapFeature.location.point
        });
        form.saveOkStream
            .map('.formData')
            .map(BU.getValueForKey('plot.geom'))
            .filter(BU.isDefined)
            .onValue(panorama.update);
    }

    var $favoriteLink = $(dom.favoriteLink),
        $favoriteIcon = $(dom.favoriteIcon);

    if (config.loggedIn) {
        $favoriteLink.on('click', function(e) {
            var wasFavorited = $favoriteLink.attr('data-is-favorited') === 'True',
                url = $favoriteLink.attr(wasFavorited ? 'data-unfavorite-url' : 'data-favorite-url');

            $.ajax({
                dataType: "json",
                url: url,
                type: 'POST'
            })
            .done(function(response) {
                // Flip classes and is-favorited attribute if request succeeded
                if (wasFavorited) {
                    $favoriteIcon.addClass('icon-star-empty');
                    $favoriteIcon.removeClass('icon-star');
                    $favoriteLink.attr('data-is-favorited', 'False');
                } else {
                    $favoriteIcon.removeClass('icon-star-empty');
                    $favoriteIcon.addClass('icon-star');
                    $favoriteLink.attr('data-is-favorited', 'True');
                }
            })
            .fail(function() {
                toastr.error('Could not save your favorite');
            });

            e.preventDefault();
        });
    }

    socialMediaSharing.init({imageFinishedStream: imageFinishedStream});

    return {
        inlineEditForm: form
    };
};
