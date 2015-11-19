"use strict";

var $ = require('jquery'),

    csrf = require('treemap/csrf'),
    BU = require('treemap/baconUtils'),
    batchModeration = require('treemap/batchModeration');

var dom = {
    filterButtons: '[data-comments-filter] li a',
    columnHeaders: '[data-comments-sort] a',
    pagingButtons: '.pagination li a'
};

$.ajaxSetup(csrf.jqueryAjaxSetupOptions);

module.exports = function(options) {
    var $container = $(options.container),

        lessOrMoreElementStream = $container.asEventStream('click', '[data-less-more]')
            .doAction('.preventDefault')
            .map('.target')
            .map($);

    lessOrMoreElementStream.onValue(function($elem) {
        $elem.text($elem.text() == 'less' ? 'more' : 'less');
        var $text = $elem.prev();
        $text.toggleClass('less');
    });

    BU.reloadContainerOnClickAndRecordUrl(
        $container, dom.pagingButtons, dom.filterButtons, dom.columnHeaders);

    return batchModeration($container);
};
