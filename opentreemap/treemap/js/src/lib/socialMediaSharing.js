// This modal does a bunch of stuff:
// * setup the social media sharing toggle button for map feature detail
// * show a modal at key times for social media sharing actions

"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    R = require('ramda'),
    _ = require('lodash'),

    _DONT_SHOW_AGAIN_KEY = 'social-media-sharing-dont-show-again',
    _SHARE_CONTAINER_SIZE = 300,

    attrs = {
        dataUrlTemplate: 'data-url-template',
        dataClass: 'data-class',
        mapFeaturePhotoDetailAbsoluteUrl: 'data-map-feature-photo-detail-absolute-url',
        mapFeaturePhotoImageAbsoluteUrl: 'data-map-feature-photo-image-absolute-url',
        mapFeaturePhotoPreview: 'data-map-feature-photo-thumbnail'
    },

    dom = {
        dontShowAgain: '[' + attrs.dataClass + '="' + _DONT_SHOW_AGAIN_KEY + '"]',
        photoModal: '#social-media-sharing-photo-upload-modal',
        photoPreview: '#social-media-sharing-photo-upload-preview',
        shareLinkSelector: '[' + attrs.dataUrlTemplate + ']',
        mapFeaturePhotoDetailAbsoluteUrl: '[' + attrs.mapFeaturePhotoDetailAbsoluteUrl + ']',
        toggle: '.share',
        container: '.js-container'
    },

    generateHref = R.curry(
        function (photoDetailUrl, photoUrl, anchor) {
            var $anchor = $(anchor),
                platform = $anchor.attr(attrs.dataClass),
                urlTemplate = $anchor.attr(attrs.dataUrlTemplate),
                url = _.template(urlTemplate)({photoDetailUrl: photoDetailUrl,
                                               photoUrl: photoUrl});
            $anchor.attr('href', url);
        }
    );

function shouldShowSharingModal() {
    if (!window.localStorage) {
        return false;
    }
    return window.localStorage.getItem(_DONT_SHOW_AGAIN_KEY) !== 'on';
}

function setDontShowAgainVal(e) {
    var dontShowAgainVal = $(e.target).val();
    window.localStorage.setItem(_DONT_SHOW_AGAIN_KEY, dontShowAgainVal);
}

function renderPhotoModal (imageData) {
    var $photoModal = $(dom.photoModal),
        $anchors = $photoModal.find(dom.shareLinkSelector),
        $carousel = $(imageData.data.result),
        $photo = $carousel.find(dom.mapFeaturePhotoDetailAbsoluteUrl),
        photoDetailUrl = $photo.attr(attrs.mapFeaturePhotoDetailAbsoluteUrl),
        photoUrl = $photo.attr(attrs.mapFeaturePhotoImageAbsoluteUrl),
        $photoPreview = $(dom.photoPreview);

    // Validation errors (image invalid, image too big) are only returned as DOM
    // elements. In order to skip showing the share dialog we need to check the
    // dialog markup for the error message element.
    if ($(imageData.data.result).filter('[data-photo-upload-failed]').length > 0) {
        return;
    }
    $photoModal.modal('show');
    $photoPreview.attr('src', $photo.attr(attrs.mapFeaturePhotoPreview));
    _.each($anchors, generateHref(photoDetailUrl, photoUrl));
}

module.exports.init = function(options) {
    var imageFinishedStream = options.imageFinishedStream || Bacon.never();
    $(dom.toggle).on('click', function () {
        $(dom.container).toggle(_SHARE_CONTAINER_SIZE);
    });

    imageFinishedStream
        .filter(shouldShowSharingModal)
        .onValue(renderPhotoModal);

    $(dom.dontShowAgain).on('click', setDontShowAgainVal);
};
