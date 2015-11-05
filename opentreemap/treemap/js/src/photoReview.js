"use strict";

var $ = require('jquery'),
    url = require('url'),
    U = require('treemap/utility'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),
    History = require('history');

var csrf = require('treemap/csrf');
$.ajaxSetup(csrf.jqueryAjaxSetupOptions);

var dom = {
    pagingButtons: '.pagination li a',
    sortHeader: '[data-photo-sort] a'
};

exports.init = function(options) {
    var $container = $(options.container);

    var photoUpdateStream = $container.asEventStream('click', '.action')
        .doAction('.preventDefault')
        .flatMap(function(e) {
            var $elem = $(e.currentTarget),
                $photo = $elem.closest('[data-photo]'),
                stream = BU.jsonRequest('POST', $elem.attr('href'))();

            stream.onValue(function(html) {
                $container.html(html);
            });

            return stream;
        });

    BU.reloadContainerOnClickAndRecordUrl($container, dom.pagingButtons, dom.sortHeader);

    return photoUpdateStream;
};
