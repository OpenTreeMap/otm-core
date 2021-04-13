"use strict";

var $ = require('jquery'),
    BU = require('treemap/lib/baconUtils.js'),
    toastr = require('toastr'),
    format = require('util').format,
    _ = require('lodash'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse'),
    photoCarousel = require('treemap/lib/photoCarousel.js');


module.exports.init = function(options) {
    var imageFinishedStream = options.imageFinishedStream,
        $imageContainer = $(options.imageContainer),
        loadImageCarouselHtml = photoCarousel.getImageCarouselLoader({
            $imageContainer: $imageContainer
        }),
        currentRotation = 0,
        $lightbox = $(options.lightbox),
        $lightboxImage = $lightbox.find('[data-photo-image]');

    imageFinishedStream.onValue(function (obj) {
        loadImageCarouselHtml(obj.data.result);
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

    function isPhotoDeletable () {
        var $deleteControl = $imageContainer.find('.item.active .delete-photo');
        return 0 < $deleteControl.length;
    }

    // Reset image rotation and buttons on opening the lightbox
    // $imageContainer.on('click', '[href="' + options.lightbox + '"]', function(e) {
    $lightbox.on('show.bs.modal', function(e) {
        var $toggle = $(e.relatedTarget),
            $active = $toggle.parents('.item.active'),
            $endpointEl = $active.find('[data-endpoint]'),
            $deleteToggleEl = $active.find('.delete-photo'),
            mode = $toggle.is($deleteToggleEl) ? 'delete' : 'view',
            endpoint = $endpointEl.attr('data-endpoint'),
            modeSelector = '[data-class="' + mode + '"]',
            notModeSelector = '[data-class]:not(' + modeSelector + ')',
            $keepControl = $lightbox.find('[data-photo-keep]'),

            label = $endpointEl.attr('data-label'),
            photoId = $endpointEl.attr('data-map-feature-photo-id'),
            featureId = $endpointEl.attr('data-map-feature-id'),
            labelSelector = '[data-class="label"]',
            labelViewSelector = '.photo-label-view',
            labelEditSelectSelector = '#photo-label-btn';

        $keepControl.off('click.delete-mode');
        currentRotation = 0;
        rotateLightboxImage(0);
        $lightbox.find('[data-photo-delete-start]').prop('disabled', true);
        $lightbox.find('[data-photo-confirm]').prop('disabled', true);

        $lightboxImage.attr('src', $endpointEl.attr('data-photo-src'));
        $lightbox.find(modeSelector).show();
        $lightbox.find(notModeSelector).hide();
        $lightbox.find('[data-photo-save]').attr('data-photo-save', endpoint);

        var labelEl = $lightbox.find(labelSelector);
        // set the label if it exists
        if(label !== undefined && label !== "") {
            var labelViewEl = $lightbox.find(labelViewSelector);
            labelViewEl.html(label);
            $lightbox.find(labelEditSelectSelector).val(label);

            $lightbox.find(labelEditSelectSelector).on('change', function(e) {
                var value = e.target.value;
                var url = reverse.Urls.map_feature_photo({
                    instance_url_name: config.instance.url_name,
                    feature_id: featureId,
                    photo_id: photId
                }) + '/label';

                var stream = BU.jsonRequest('POST', url)({'label': value});
                stream.onValue(function() {
                    console.log("done");
                });
            });

            if (mode === 'edit'){
                labelViewEl.hide();
            } else {
                labelViewEl.show();
            }

            labelEl.show();

        } else {
            labelEl.hide();
        }

        // tzinckgraf
        if (1 === $deleteToggleEl.length) {
            $lightbox.find('[data-photo-confirm]').attr('data-photo-confirm', endpoint);
            $lightbox.find('[data-class="delete"] button').prop('disabled', false);
            $lightbox.find('[data-photo-delete-start]').prop('disabled', false);

            if (mode === 'delete') {
                $keepControl.one('click.delete-mode', function () {
                    $lightbox.modal('hide');
                });
            }
        } else {
            $lightbox.find('[data-photo-confirm]').attr('data-photo-confirm', '');
        }
    });

    $lightbox.on('click', '[data-photo-edit]', function() {
        $lightbox.find('[data-class]:not([data-class="edit"])').hide();
        $lightbox.find('[data-class="edit"]').show();
    });

    $lightbox.on('click', '[data-photo-save-cancel]', function() {
        $lightbox.find('[data-class]:not([data-class="view"])').hide();
        $lightbox.find('[data-class="view"]').show();
    });

    $lightbox.on('click', '[data-photo-rotate]', function(e) {
        var $target = $(e.currentTarget),
            $saveButton = $target
		.parents('.lightbox-caption')
		.find('[data-photo-save]')
		.first(),
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

    $lightbox.on('click', '[data-photo-keep]', function(e) {
        $lightbox.find('[data-class]:not([data-class="view"])').hide();
        $lightbox.find('[data-class="view"]').show();
    });

    $lightbox.on('click', '[data-photo-delete-start]', function(e) {
        $lightbox.find('[data-class]:not([data-class="delete"])').hide();
        $lightbox.find('[data-class="delete"]').show();
    });

    $lightbox.on('click', '[data-photo-confirm]:not([data-photo-confirm=""])', function(e) {
        var $button = $(e.target);

        $lightbox.find('button[data-class="delete"]').prop('disabled', true);

        $.ajax({
            method: 'DELETE',
            url: $button.attr('data-photo-confirm')
        })
        .done(function(data) {
            $lightbox.modal('hide');
            loadImageCarouselHtml(data);
        });
    });
};
