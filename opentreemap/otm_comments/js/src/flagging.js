"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),

    COMMENTS_CONTAINER = '#comments-container',
    FLAG_TOGGLE_CONTAINER = 'div[data-class="comment-flag"]',
    FLAG_TOGGLE_ANCHOR = 'a[data-class="comment-flag-toggle"]',
    SAVING_MESSAGE = "Saving...";

module.exports = function(options) {
    $(COMMENTS_CONTAINER)
        .asEventStream('click', FLAG_TOGGLE_ANCHOR)
        .doAction('.preventDefault')
        .map('.target').map($).onValue(function($el) {
            var $parent = $el.parents(FLAG_TOGGLE_CONTAINER),
                url = $el.attr('href');
            $parent.html(SAVING_MESSAGE);
            $parent.load(url, {});
        });
};
