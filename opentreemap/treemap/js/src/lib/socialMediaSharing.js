// This modal does a bunch of stuff:
// * setup the social media sharing toggle button for map feature detail
// * show a modal at key times for social media sharing actions

"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    BU = require('treemap/lib/baconUtils.js'),
    R = require('ramda'),
    _ = require('lodash'),
    reverse = require('reverse'),
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
        mapFeatureId: 'data-map-feature-id',
        mapFeaturePhotoId: 'data-map-feature-photo-id',
        mapFeaturePhotoDetailAbsoluteUrl: 'data-map-feature-photo-detail-absolute-url',
        mapFeaturePhotoImageAbsoluteUrl: 'data-map-feature-photo-image-absolute-url',
        mapFeaturePhotoPreview: 'data-map-feature-photo-thumbnail',
    },

    dom = {
        dontShowAgain: '[' + attrs.dataClass + '="' + _DONT_SHOW_AGAIN_KEY + '"]',
        photoModal: '#social-media-sharing-photo-upload-modal',
        photoPreview: '#label-photo-upload-preview',
        shareLinkSelector: '[' + attrs.dataUrlTemplate + ']',
        mapFeatureId: '[' + attrs.mapFeatureId + ']',
        mapFeaturePhotoId: '[' + attrs.mapFeaturePhotoId + ']',
        mapFeaturePhotoDetailAbsoluteUrl: '[' + attrs.mapFeaturePhotoDetailAbsoluteUrl + ']',
        toggle: '.share',
        container: '.js-container',
        photoLabel: '#photo-label'
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

        mapFeatureId = $photo.attr(attrs.mapFeatureId),
        mapFeaturePhotoId = $photo.attr(attrs.mapFeaturePhotoId),

        $photoPreview = $(dom.photoPreview);

    photoInfo.PhotoDetailUrl = photoDetailUrl;
    photoInfo.PhotoUrl = photoUrl;


    // Validation errors (image invalid, image too big) are only returned as DOM
    // elements. In order to skip showing the share dialog we need to check the
    // dialog markup for the error message element.
    //if ($(imageData.data.result).filter('[data-photo-upload-failed]').length > 0) {
    //    return;
    //}
    $photoModal.modal('show');
    $photoPreview.attr('src', $photo.attr(attrs.mapFeaturePhotoPreview));
    _.each($anchors, generateHref(photoDetailUrl, photoUrl));

    // remove the old handlers and reset the value
    $(dom.photoLabel).off('change');
    $(dom.photoLabel).val('');

    $(dom.photoLabel).on('change', function(e) {
        var value = e.target.value;
        var url = reverse.Urls.map_feature_photo({
            instance_url_name: config.instance.url_name,
            feature_id: window.otm.mapFeature.featureId,
            photo_id: mapFeaturePhotoId
        }) + '/label';

        var stream = BU.jsonRequest('POST', url)({'label': value});
        stream.onValue(function() {
            console.log("done");
        });

        /*
        var addStream = $addUser
            .asEventStream('click')
            .map(function () {
                return {'email': $addUserEmail.val()};
            })
            .flatMap(BU.jsonRequest('POST', url));
        */

    });
}


module.exports.init = function(options) {
    var imageFinishedStream = options.imageFinishedStream || Bacon.never();
    $(dom.toggle).on('click', function () {
        $(dom.container).toggle(_SHARE_CONTAINER_SIZE);
    });

    imageFinishedStream.onValue(renderPhotoModal);
    //.filter(shouldShowSharingModal)

    $(dom.dontShowAgain).on('click', setDontShowAgainVal);
};
