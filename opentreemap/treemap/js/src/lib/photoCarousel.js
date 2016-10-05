// Manage panel for image uploading
"use strict";

var $ = require('jquery');


module.exports.getImageCarouselLoader = function (options) {
    var $imageContainer = options.$imageContainer;

    return function (data) {
        if ($imageContainer.length > 0) {
            $imageContainer.html(data);
            // We need to remove the cached data because Bootstrap stores
            // the carousel-indicators, and adds the active class onto its
            // stored fragments
            $imageContainer.removeData('carousel');
        }
    };
};
