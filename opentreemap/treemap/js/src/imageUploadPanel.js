// Manage panel for image uploading

"use strict";

// For modal dialog on jquery
require('bootstrap');

var $ = require('jquery'),
    Bacon = require('baconjs'),
    format = require('util').format,
    U = require('treemap/utility'),
    _ = require('lodash');

// jQuery-File-Upload and its dependencies
require('jqueryUiWidget');
require('jqueryIframeTransport');
require('jqueryFileUpload');

module.exports.init = function(options) {
    var $panel = $(options.panelId),
        $image = $(options.imageElement),
        $error = $(options.error),
        $imageContainer = $(options.imageContainer),
        dataType = options.dataType || 'json',

        $chooser = $panel.find('.fileChooser'),
        $progressBar = $panel.find('.progress').children().first(),
        callback,
        finishedStream = new Bacon.EventStream(function(subscribe) {
            callback = subscribe;

            return function() { callback = null; };
        }),

        currentRotation = 0,
        $lightbox = $(options.lightbox),
        $lightboxImage = $lightbox.find('[data-photo-image]');

    function loadImageCarouselHtml(data) {
        if ($imageContainer.length > 0) {
            $imageContainer.html(data);
            // We need to remove the cached data because Bootstrap stores
            // the carousel-indicators, and adds the active class onto its
            // stored fragments
            $imageContainer.removeData('carousel');
        }
    }
    $chooser.fileupload({
        dataType: dataType,
        start: function () {
            $error.hide();
        },
        progressall: function (e, data) {
            var progress = parseInt(data.loaded / data.total * 100, 10);
            $progressBar.width(progress + '%');
        },
        always: function (e, data) {
            $panel.modal('hide');
            $progressBar.width('0%');

            loadImageCarouselHtml(data.result);
        },
        done: function (e, data) {
            if ($image.length > 0) {
                $image.attr('src', data.result.url);
            }

            if (callback) {
                // Downstream users will be opening modals, which leads to
                // style errors if that is done before a modal closes
                $panel.one('hidden.bs.modal', function() {
                    callback(new Bacon.Next({event: e, data: data}));
                });
            }
        },
        fail: function (e, data) {
            // If the datatype is not JSON we expect the endpoint to return
            // error messages inside the HTML fragment it gives back
            if (dataType == 'json') {
                var json = data.jqXHR.responseJSON,
                    message;

                if (json && json.error) {
                    U.warnDeprecatedErrorMessage(json);
                    message = json.error;
                } else if (json && json.globalErrors) {
                    message = json.globalErrors.join(',');
                } else {
                    message = "Unable to upload image";
                }
                $error.text(message).show();
            }
        }
    });

    $imageContainer.on('slide', function(e) {
        var $thumbnailList = $imageContainer.find('.carousel-indicators'),
            $thumbnailListContainer = $thumbnailList.parent(),
            index = $imageContainer.find('.carousel-inner .item').index(e.relatedTarget),
            $thumbnail = $thumbnailList.find('[data-slide-to="' + index + '"]'),

            // The $thumbnailListContainer has overflow-x:auto on it, and
            // we want to scroll it so the currently selected thumbnail is
            // around the center.  This was arrived at via trial and error,
            // it could probably be tweaked to be a bit better.
            // The 1.65 makes everything work, but is likely tied to the
            // thumbnail width.
            scrollOffset = $thumbnail.offset().left + $thumbnail.width() -
                ($thumbnailList.offset().left + $thumbnailListContainer.innerWidth() / 1.65);

        // Bootstrap Carousel's animations are hardcoded to .6 seconds,
        // which we should match when animating thumbnails
        $thumbnailListContainer.animate({'scrollLeft': scrollOffset}, 600);
    });

    // To make the thumbnail scrolling work we need to prevent wrapping
    // from the first to the last item, and vice versa
    $imageContainer.on('slid', function(e) {
        var isFirst = $imageContainer.find('.carousel-inner .item:first').hasClass('active'),
            isLast = $imageContainer.find('.carousel-inner .item:last').hasClass('active');
        $imageContainer
            .find('.carousel-control')
            .attr('href', '#' + $imageContainer.attr('id'))
            .removeClass('disabled');
        if (isFirst) {
            $imageContainer
                .find('.carousel-control.left')
                .attr('href', '')
                .addClass('disabled');
        } else if (isLast) {
            $imageContainer
                .find('.carousel-control.right')
                .attr('href', '')
                .addClass('disabled');
        }
    });

    function rotateLightboxImage(degrees) {
        var rotationProperty = format('rotate(%ddeg)', degrees);

        $lightboxImage.css({
            '-webkit-transform': rotationProperty,
            '-moz-transform': rotationProperty,
            '-ms-transform': rotationProperty,
            'transform': rotationProperty
        });
    }

    // Reset image rotation  and buttons on opening the lightbox
    $imageContainer.on('click', '[href="' + options.lightbox + '"]', function(e) {
        var $toggle = $(this),
        endpoint = $toggle.attr('data-endpoint');

        e.preventDefault();

        currentRotation = 0;
        rotateLightboxImage(0);
        $lightboxImage.attr('src', $toggle.attr('data-photo-src'));
        $lightbox.find('[data-class="view"]').show();
        $lightbox.find('[data-class="edit"]').hide();
        $lightbox.find('[data-photo-save]').attr('data-photo-save', endpoint);
    });
    $lightbox.on('click', '[data-class="view"]', function() {
        $lightbox.find('[data-class="view"]').hide();
        $lightbox.find('[data-class="edit"]').show();
    });

    $lightbox.on('click', '[data-photo-rotate]', function(e) {
        var $target = $(e.currentTarget),
            $saveButton = $target.siblings('[data-photo-save]').first(),
            degrees = parseInt($target.attr('data-photo-rotate'), 10);

        currentRotation = (360 + currentRotation + degrees) % 360;
        rotateLightboxImage(currentRotation);

        // Don't allowing saving if there is no rotation to be done
        if (currentRotation === 0) {
            $saveButton.prop('disabled', true);
        } else {
            $saveButton.prop('disabled', false);
        }
    });

    $lightbox.on('click', '[data-photo-save]', function(e) {
        var $button = $(e.target),
            // CSS rotations are reversed from the backend rotations
            degreesToSave = -currentRotation;

        $button.prop('disabled', true);  // Prevent double submissions

        $.ajax({
            method: 'POST',
            url: $button.attr('data-photo-save'),
            data: {'degrees': degreesToSave}
        })
        .done(function(data) {
            $lightbox.modal('hide');
            loadImageCarouselHtml(data);
        });
    });

    return finishedStream;
};
