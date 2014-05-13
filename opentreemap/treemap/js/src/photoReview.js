"use strict";

var $ = require('jquery'),
    U = require('treemap/utility'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),
    History = require('history');

var csrf = require('treemap/csrf');
$.ajaxSetup(csrf.jqueryAjaxSetupOptions);

exports.init = function(options) {
    var updatePageFromUrl = new Bacon.Bus(),
        url = options.url,
        nextPhotoUrl = options.nextPhotoUrl,
        initialPageStream = updatePageFromUrl
            .map(U.parseQueryString)
            .map('.n')
            .filter(BU.id);

    window.addEventListener('popstate', function(event) {
        updatePageFromUrl.push();
    }, false);

    function showErrorMessage(msg) {
        $('.errors').html(msg);
    }

    function getReviewMarkupForNextPhoto() {
        var n = U.parseQueryString.n || 1;
        return BU.jsonRequest('GET', nextPhotoUrl)({n: n});
    }

    $('body').on('click', '.action', function(e) {
        e.preventDefault();
        var $li = $(this).closest('li');

        var stream = BU.jsonRequest('POST', $(this).attr('href'))();

        stream.onValue(function() {
            $li.remove();
        });
        stream.onError(showErrorMessage);

        stream
            .flatMap(getReviewMarkupForNextPhoto)
            .map($)
            .onValue($('ul.thumbnails'), 'append');
    });

    function createPageUpdateStream(initialPageStream) {
        var pageStream = $('.pagination ul li')
                .asEventStream('click')
                .map('.target')
                .map($)
                .map('.data', 'page');

        pageStream
            .map(function(n) { return '?n=' + n; })
            .onValue(function (url) {
                History.pushState(null, document.title, url);
            });

        var pageUpdateStream = pageStream
                .merge(initialPageStream)
                .map(function(n) { return {'n': n}; })
                .flatMap(BU.jsonRequest('GET', url));

        pageUpdateStream
            .onValue($('.content'), 'html');

        pageUpdateStream
            .onValue(createPageUpdateStream, initialPageStream);

        return pageUpdateStream;
    }

    createPageUpdateStream(initialPageStream);
};
