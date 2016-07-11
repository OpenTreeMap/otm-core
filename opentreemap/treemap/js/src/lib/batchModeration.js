"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),

    csrf = require('treemap/lib/csrf.js'),
    BU = require('treemap/lib/baconUtils.js');

$.ajaxSetup(csrf.jqueryAjaxSetupOptions);

module.exports = function(container) {
    var $container = $(container),

        singleActionStream = $container.asEventStream('click', '[data-single-action] a.action'),
        batchActionStream = $container.asEventStream('click', '[data-batch-action] a'),
        toggleAllEventStream = $container.asEventStream('click', '[data-toggle-all]'),

        actionUrlStream = Bacon.mergeAll(singleActionStream, batchActionStream)
            .doAction('.preventDefault')
            .map('.target.href')
            .filter(BU.isDefinedNonEmpty),

        singleActionIdStream = singleActionStream
            .map('.target')
            .map($)
            .map(function($elem) {
                return [$elem.parents('[data-id]').attr('data-id')];
            }),

        getSelectedIds = function() {
            var $selectedCheckboxes = $container
                .find('[data-id]')
                .has('[data-batch-action-checkbox]:checked');

            return _.map($selectedCheckboxes, function(elem) {
                return $(elem).attr('data-id');
            });
        },

        batchActionIdStream = batchActionStream
            .map(getSelectedIds),

        actionIdStream = Bacon.mergeAll(singleActionIdStream, batchActionIdStream)
            .map(function(array) {
                return {'ids': array.join(',')};
            }),

        actionResultStream = Bacon.zipAsArray(actionUrlStream, actionIdStream);

    toggleAllEventStream
        .map($container, 'find', '[data-batch-action-checkbox]')
        .onValue(function($elems) {
            var checked = $container.find('[data-toggle-all]').is(':checked');
            $elems.prop('checked', checked);
        });

    var containerUpdatedStream = actionResultStream.flatMap(function(req) {
        var promise = $.post(req[0], req[1], function(html) {
            $container.html(html);
        });
        return Bacon.fromPromise(promise);
    });

    // We need an onValue to force evaluation of the lazy stream
    containerUpdatedStream.onValue($.noop);

    return containerUpdatedStream;
};
