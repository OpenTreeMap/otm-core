"use strict";

var $ = require('jquery'),
    U = require('./utility'),
    Bacon = require('baconjs'),
    BU = require('BaconUtils');

var csrf = require('csrf');
$.ajaxSetup(csrf.jqueryAjaxSetupOptions);


function getReviewMarkupForNextPhoto() {
    var n = U.parseQueryString.n || 1;
    var nextPhotoAddress = 'next';
    return BU.jsonRequest('GET', nextPhotoAddress)({n: n});
}

exports.init = function() {
    var updatePageFromUrl = new Bacon.Bus();
    var initialPageStream = updatePageFromUrl
            .map(U.parseQueryString)
            .map('.n')
            .filter(BU.id);

    window.addEventListener('popstate', function(event) {
        updatePageFromUrl.push();
    }, false);

    function showErrorMessage(msg) {
        $('.errors').html(msg);
    }

    $('body').on('click', '.action', function(e) {
        e.preventDefault();
        var $li = $(this).closest('li');
        $li.hide();

        var stream = BU.jsonRequest('POST', $(this).attr('href'))();

        stream.onError($li, 'show');
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
            .onValue(U.pushState);

        var pageUpdateStream = pageStream
                .merge(initialPageStream)
                .map(function(n) { return {'n': n}; })
                .flatMap(BU.jsonRequest('GET', 'partial'));

        pageUpdateStream
            .onValue($('.content'), 'html');

        pageUpdateStream
            .onValue(createPageUpdateStream, initialPageStream);

        return pageUpdateStream;
    }

    createPageUpdateStream(initialPageStream);
};
