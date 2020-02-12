// This modal does a bunch of stuff:
// * setup the social media sharing toggle button for map feature detail
// * show a modal at key times for social media sharing actions

"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    R = require('ramda'),
    _ = require('lodash'),
    config = require('treemap/lib/config.js'),

    _DONT_SHOW_AGAIN_KEY = 'social-media-sharing-dont-show-again',
    _SHARE_CONTAINER_SIZE = 300,

    // for iNaturalist
    _APP_ID = 'db6db69ef86d5a21a4c9876bcaebad059db3b1ed90f30255c6d9e8bdaebf0513',

    photoInfo = {
        PhotoDetailUrl: '',
        PhotoUrl: ''
    },

    attrs = {
        dataUrlTemplate: 'data-url-template',
        dataClass: 'data-class',
        mapFeaturePhotoDetailAbsoluteUrl: 'data-map-feature-photo-detail-absolute-url',
        mapFeaturePhotoImageAbsoluteUrl: 'data-map-feature-photo-image-absolute-url',
        mapFeaturePhotoPreview: 'data-map-feature-photo-thumbnail'
    },

    dom = {
        dontShowAgain: '[' + attrs.dataClass + '="' + _DONT_SHOW_AGAIN_KEY + '"]',
        loginToINaturalist: '[' + attrs.dataClass + '="social-media-login-to-inaturalist"]',
        submitToINaturalist: '[' + attrs.dataClass + '="social-media-submit-to-inaturalist"]',
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

    photoInfo.PhotoDetailUrl = photoDetailUrl;
    photoInfo.PhotoUrl = photoUrl;

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

function loginToINaturalist(e) {
    // run the auth
    var site = "https://www.inaturalist.org";
    var redirectUri = "http://localhost:7070/jerseycity/inaturalist/";
    /*
    // For PKCE workflow, just in the client side
    var codeVerifier = 'test';
    var codeChallenge = window.btoa(codeVerifier);
    var url = `${site}/oauth/authorize?client_id=${_APP_ID}&redirect_uri=${redirectUri}&response_type=code&code_challenge_method=S256&code_challenge=${codeChallenge}`
    */
    var url = `${site}/oauth/authorize?client_id=${_APP_ID}&redirect_uri=${redirectUri}&response_type=code`

    window.location.href = url;
}

function submitToINaturalist(e) {
    var featureId = window.otm.mapFeature.featureId,
        inaturalistUrl = '/jerseycity/inaturalist-add/';

    var data = {
        'photoDetailUrl': photoInfo.PhotoDetailUrl,
        'photoUrl': photoInfo.PhotoUrl,
        'featureId': featureId
    };
    console.log(data);

    $.ajax({
        url: inaturalistUrl,
        type: 'POST',
        contentType: "application/json",
        data: JSON.stringify(data),
        success: onSuccess,
        error: onError
    });

    console.log("here");
}

function onSuccess(result) {
    console.log('success');
    console.log(result);
}

function onError(result) {
    console.log('error');
    console.log(result);
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
    $(dom.loginToINaturalist).on('click', loginToINaturalist);
    $(dom.submitToINaturalist).on('click', submitToINaturalist);
};
