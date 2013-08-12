"use strict";

exports.concat = function (s1, s2) {
    return s1 + s2;
};

exports.pushState = function (url) {
    history.pushState({}, '', url);
};

exports.parseQueryString = function () {
    var match,
        pl     = /\+/g,  // Regex for replacing addition symbol with a space
        search = /([^&=]+)=?([^&]*)/g,
        decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
        query  = window.location.search.substring(1),
        urlParams = {};

    while ((match = search.exec(query))) {
        urlParams[decode(match[1])] = decode(match[2]);
    }

    return urlParams;
};
