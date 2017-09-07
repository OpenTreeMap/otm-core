"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    toastr = require('toastr'),
    plotDetail = require('treemap/lib/plotDetail.js'),
    resourceDetail = require('treemap/lib/resourceDetail.js'),
    inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    MapManager = require('treemap/lib/MapManager.js'),
    R = require('ramda'),
    BU = require('treemap/lib/baconUtils.js'),
    Bacon = require('baconjs'),
    U = require('treemap/lib/utility.js'),
    FH = require('treemap/lib/fieldHelpers.js'),
    geometryMover = require('treemap/lib/geometryMover.js'),
    plotMarker = require('treemap/lib/plotMarker.js'),
    statePrompter = require('treemap/lib/statePrompter.js'),
    csrf = require('treemap/lib/csrf.js'),
    uploadPanel = require('treemap/lib/uploadPanel.js'),
    imageLightbox = require('treemap/lib/imageLightbox.js'),
    socialMediaSharing = require('treemap/lib/socialMediaSharing.js'),
    reverseGeocodeStreamAndUpdateAddressesOnForm =
        require('treemap/lib/reverseGeocodeStreamAndUpdateAddressesOnForm.js'),
    streetView = require('treemap/lib/streetView.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse'),
    alerts = require('treemap/lib/alerts.js'),
    buttonEnabler = require('treemap/lib/buttonEnabler.js'),
    comments = require('otm_comments/lib/comments.js');

// Placed onto the jquery object
require('bootstrap-datepicker');

var dom = {
        favoriteLink: '#favorite-link',
        favoriteIcon: '#favorite-star',
        detail: '#mapFeaturePartial',
        sidebar: '#sidebar',
        form: '#map-feature-form',
        streetView: '#street-view',
        location: {
            edit: '#edit-location',
            cancel: '#cancel-edit-location',
        },
        polygonAreaDisplay: '.js-area'
    };

function init() {
    var detailUrl = window.location.href;

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

    var imageFinishedStream = uploadPanel.init({
        dataType: 'html'
    });

    imageLightbox.init({
        imageFinishedStream: imageFinishedStream,
        imageContainer: '#photo-carousel',
        lightbox: '#photo-lightbox'
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
        dontUpdateOnSaveOk: true
    });

    function initDetailAfterRefresh() {
        buttonEnabler.run();
        FH.initMultiChoice($('[data-class="edit"]'), $('[data-class="display"]'));
        $("input[data-date-format]").datepicker();
        initDetail();
    }

    function initDetail() {
        if (window.otm.mapFeature.isPlot) {
            plotDetail.init(form);
        } else {
            resourceDetail.init(form);
        }
        updateFavoritedState(isFavoriteNow());
    }

    initDetail(form);

    var refreshDetailUrl = reverse.map_feature_detail_partial({
            instance_url_name: config.instance.url_name,
            feature_id: window.otm.mapFeature.featureId
        }),
        refreshSidebarUrl = reverse.map_feature_sidebar({
            instance_url_name: config.instance.url_name,
            feature_id: window.otm.mapFeature.featureId
        });
    form.saveOkStream.merge(imageFinishedStream)
        .onValue(function () {
            $(dom.detail).load(refreshDetailUrl, initDetailAfterRefresh);
            $(dom.sidebar).load(refreshSidebarUrl);
        });

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

    if (window.otm.mapFeature.startInEditMode) {
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
        centerWM: window.otm.mapFeature.location.point,
        zoom: mapManager.ZOOM_PLOT
    });

    var moverOptions = {
        mapManager: mapManager,
        inlineEditForm: form,
        editLocationButton: dom.location.edit,
        cancelEditLocationButton: dom.location.cancel,
        resourceType: window.otm.mapFeature.resourceType,
        location: window.otm.mapFeature.location
    };

    if (window.otm.mapFeature.isEditablePolygon) {
        currentMover = geometryMover.polygonMover(moverOptions);
        currentMover.editor.areaStream.onValue(showUpdatedArea);
    } else {
        plotMarker.init(mapManager.map);
        plotMarker.useTreeIcon(window.otm.mapFeature.useTreeIcon);
        reverseGeocodeStreamAndUpdateAddressesOnForm(plotMarker.moveStream, dom.form);
        moverOptions.plotMarker = plotMarker;
        currentMover = geometryMover.plotMover(moverOptions);
    }

    var detailUrlPrefix = U.removeLastUrlSegment(detailUrl),
        clickedIdStream = mapManager.map.utfEvents
            .map('.data.' + config.utfGrid.mapfeatureIdKey)
            .filter(BU.isDefinedNonEmpty);

    clickedIdStream
        .filter(BU.not, window.otm.mapFeature.featureId)
        .map(_.partialRight(U.appendSegmentToUrl, detailUrlPrefix, false))
        .filter(R.complement(currentMover.isEnabled))
        .onValue(_.bind(window.location.assign, window.location));

    if (config.instance.basemap.type === 'google') {
        var $streetViewContainer = $(dom.streetView);
        $streetViewContainer.show();
        var panorama = streetView.create({
            streetViewElem: $streetViewContainer[0],
            noStreetViewText: config.trans.noStreetViewText,
            location: window.otm.mapFeature.location.point
        });
        form.saveOkStream
            .onValue(function () {
                // If location is an array, we are editing a polygonal map
                // feature. The page triggers a full postback after editing a
                // polygon map feature.
                if (!_.isArray(currentMover.location)) {
                    panorama.update(currentMover.location);
                }
            });
    }

    handleFavoriteClick();

    socialMediaSharing.init({
        imageFinishedStream: imageFinishedStream
    });
}

function isFavoriteNow() {
    return $(dom.favoriteLink).attr('data-is-favorited') === 'True';
}

function updateFavoritedState(isFavorite) {
    var $favoriteLink = $(dom.favoriteLink),
        $favoriteIcon = $(dom.favoriteIcon),
        title = $favoriteLink.attr(
            isFavorite ? 'data-favorite-title' : 'data-unfavorite-title');

    $favoriteIcon.attr('title', title);

    if (isFavorite) {
        $favoriteIcon.removeClass('icon-star-empty');
        $favoriteIcon.addClass('icon-star');
        $favoriteLink.attr('data-is-favorited', 'True');
    } else {
        $favoriteIcon.addClass('icon-star-empty');
        $favoriteIcon.removeClass('icon-star');
        $favoriteLink.attr('data-is-favorited', 'False');
    }
}

function handleFavoriteClick() {
    if (config.loggedIn) {
        $('body').on('click', dom.favoriteLink, function (e) {
            var wasFavorited = isFavoriteNow(),
                url = $(dom.favoriteLink)
                    .attr(wasFavorited ? 'data-unfavorite-url' : 'data-favorite-url');

            $.ajax({
                dataType: "json",
                url: url,
                type: 'POST'
            })
                .done(function (response) {
                    updateFavoritedState(!wasFavorited);
                })
                .fail(function () {
                    toastr.error('Could not save your favorite');
                });

            e.preventDefault();
        });
    }
}

function showUpdatedArea(area) {
    $(dom.polygonAreaDisplay).html(area);
}

init();
