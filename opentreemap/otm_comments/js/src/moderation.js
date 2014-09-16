"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),

    BU = require('treemap/baconUtils');

module.exports = function(options) {
    var $container = $(options.container),

        lessOrMoreElementStream = $container.asEventStream('click', '[data-less-more]')
            .doAction('.preventDefault')
            .map('.target')
            .map($),

        // We use event delegation on the outer container, because we replace
        // the entire table including the pagination and filter section.
        //
        // We prevent default events for everything, but only get new pages
        // for anchor tags which have href values
        pageEventStream = $container.asEventStream('click', '.pagination li a'),
        filterEventStream = $container.asEventStream('click', '[data-comments-filter] li a'),
        sortingEventStream = $container.asEventStream('click', '[data-comments-sort] th a'),

        urlStream = Bacon.mergeAll(pageEventStream, filterEventStream, sortingEventStream)
            .doAction('.preventDefault')
            .map('.target')
            .map('.href')
            .filter(BU.isDefinedNonEmpty);

    lessOrMoreElementStream.onValue(function($elem) {
        $elem.text($elem.text() == 'less' ? 'more' : 'less');
        var $text = $elem.prev();
        $text.toggleClass('less');
    });

    urlStream.onValue($container, 'load');
};
