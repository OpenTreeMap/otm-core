// Photo deletion consists of a series of steps:
// * All is contingent on whether the current user uploaded the photo,
//   or has administrative privilege
// * On hover over the `imageContainer`, show the trash button
// * Clicking the trash button shows a confirm modal
// * Confirmation
//   + sends a DELETE request to the server
//   + starts a stream for the DELETE response
//   + disables the footer confirmation controls and dismissal x
// * The stream from a successful DELETE response
//   + dismisses the modal
//   + removes the photo from the carousel and carousel indicators
// * The stream from a failed DELETE response
//   + shows an error message in the modal
//   + leaves the positive confirmation control disabled
//   + enables the cancelation control and dismissal x
// * Don't show the trash button if there are no photos in the carousel
// * Dismissing the modal without confirming leaves everything in the
//   state from before clicking the trash button, whether it is before
//   confirmation, or after a failed DELETE response

"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),
    photoCarousel = require('treemap/lib/photoCarousel.js');


module.exports.init = function(options) {
    var data = {
        endpoint: 'endpoint'
    },
    callback,
    finishedStream = new Bacon.EventStream(function(subscribe) {
        callback = subscribe;

        return function() {
            callback = null;
        };
    }),

    dom = {
        imageContainer: options.imageContainer,
        photoDeleteConfirmModal: options.modal,
        activeItem: '.item.active',
        photoDeleteConfirmPreview: '#photo-to-delete-preview',
        photoDeleteFailureMessage: '#photo-delete-failure-message',
        photoDeleteConfirmControl: '[data-class="confirmed-photo-delete"]',
        photoDismissConfirmControls: '[data-dismiss="modal"]'
    },

    $deleteConfirmModal = $(dom.photoDeleteConfirmModal),
    $body = $deleteConfirmModal.parents('body'),

    els = {
        $imageContainer: $(dom.imageContainer),
        $deleteConfirmModal: $deleteConfirmModal,
        $deleteConfirmPreview: $(dom.photoDeleteConfirmPreview),
        $deleteConfirmControl: $deleteConfirmModal.find(dom.photoDeleteConfirmControl),
        $deleteDismissControls: $deleteConfirmModal.find(dom.photoDismissConfirmControls),
        $deleteFailureMessage: $deleteConfirmModal.find(dom.photoDeleteFailureMessage)
    },
    loadImageCarouselHtml = photoCarousel.getImageCarouselLoader({
        $imageContainer: els.$imageContainer
    });

    function renderDeletePhotoConfirmModal () {
        var $activePhoto = els.$imageContainer.find(dom.activeItem),
            $photoLink = $activePhoto.children('a'),
            $photoThumb = $photoLink.children('img'),

            photoEndpoint = $photoLink.data(data.endpoint),
            photoThumbUrl = $photoThumb.attr('src');

        // reset
        els.$deleteConfirmControl.removeProp('disabled');
        els.$deleteDismissControls.removeProp('disabled');
        els.$deleteFailureMessage.addClass('hidden');

        els.$deleteConfirmPreview.attr('src', photoThumbUrl);
        els.$deleteConfirmControl.data(data.endpoint, photoEndpoint);
    }

    function initiateDelete (ev) {
        var $confirmControl = $(ev.target),
            endpoint = $confirmControl.data(data.endpoint);

        ev.stopPropagation();
        ev.preventDefault();

        els.$deleteConfirmControl.prop('disabled', true);
        els.$deleteDismissControls.prop('disabled', true);

        $.ajax({
            method: 'DELETE',
            url: endpoint
        })
        .then(function (data) {
            $deleteConfirmModal.modal('hide');
            loadImageCarouselHtml(data);
        }, function () { // failure
            els.$deleteConfirmControl.removeProp('disabled');
            els.$deleteDismissControls.removeProp('disabled');
            els.$deleteFailureMessage.removeClass('hidden');
        });
    }

    $body.on('click', dom.photoDeleteConfirmModal + ' ' + dom.photoDeleteConfirmControl, initiateDelete);
    $body.on('show.bs.modal', dom.photoDeleteConfirmModal, renderDeletePhotoConfirmModal);

    return finishedStream;
};
