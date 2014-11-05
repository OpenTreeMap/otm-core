"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),

    csrf = require('treemap/csrf'),
    BU = require('treemap/baconUtils');

var dom = {
    filterButtons: '[data-comments-filter] li a',
    columnHeaders: '[data-comments-sort] th a',
    pagingButtons: '.pagination li a'
};

$.ajaxSetup(csrf.jqueryAjaxSetupOptions);

module.exports = function(options) {
    var $container = $(options.container),

        lessOrMoreElementStream = $container.asEventStream('click', '[data-less-more]')
            .doAction('.preventDefault')
            .map('.target')
            .map($),

        // We use event delegation on the outer container, because we replace
        // the entire table including the pagination and filter section.

        singleActionStream = $container.asEventStream('click', '[data-comment-single-action] a'),
        batchActionStream = $container.asEventStream('click', '[data-comment-batch] a'),
        toggleAllEventStream = $container.asEventStream('click', '[data-comment-toggle-all]'),

        actionUrlStream = Bacon.mergeAll(singleActionStream, batchActionStream)
            .doAction('.preventDefault')
            .map('.target.href')
            .filter(BU.isDefinedNonEmpty)
            .map(function(url) {
                // We have to look this up every time because it changes based
                // on the current filter/sort/page
                var params = $container.find('[data-comments-params]').attr('data-comments-params');
                return url + '?' + params;
            }),

        singleActionIdStream = singleActionStream
            .map('.target')
            .map($)
            .map(function($elem) {
                return [$elem.parents('[data-comment-id]').attr('data-comment-id')];
            }),

        getSelectedCommentIds = function() {
            var $selectedCheckboxes = $container
                .find('[data-comment-id]')
                .has('[data-batch-action-checkbox]:checked');

            return _.map($selectedCheckboxes, function(elem) {
                return $(elem).attr('data-comment-id');
            });
        },

        batchActionIdStream = batchActionStream
            .map(getSelectedCommentIds),

        actionIdStream = Bacon.mergeAll(singleActionIdStream, batchActionIdStream)
            .map(function(array) {
                return {'comment-ids': array.join(',')};
            }),

        actionResultStream = Bacon.zipAsArray(actionUrlStream, actionIdStream);

    lessOrMoreElementStream.onValue(function($elem) {
        $elem.text($elem.text() == 'less' ? 'more' : 'less');
        var $text = $elem.prev();
        $text.toggleClass('less');
    });

    BU.reloadOnClick($container, dom.pagingButtons, dom.filterButtons, dom.columnHeaders);

    actionResultStream.onValues(_.bind($container.load, $container));

    toggleAllEventStream
        .map($container, 'find', '[data-batch-action-checkbox]')
        .onValue(function($elems) {
            var checked = $container.find('[data-comment-toggle-all]').is(':checked');
            $elems.prop('checked', checked);
        });
};
