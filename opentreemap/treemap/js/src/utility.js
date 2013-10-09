"use strict";

var Url = require('url'),
    QS = require('querystring'),
    $ = require('jquery');

exports.getUpdatedQueryString = function (k, v) {
    var url = Url.parse(window.location.href, true);
    var query = url.query || {};

    query[k] = v;

    return QS.stringify(query);
};

exports.getUpdateUrlByUpdatingQueryStringParam = function (k, v) {
    var url = Url.parse(window.location.href, true);
    var query = url.query || {};

    if (v === null) {
        delete query[k];
    } else {
        query[k] = v;
    }

    url.query = query;
    url.search = null;

    return Url.format(url);
};

exports.getLastUrlSegment = function(url) {
    var parts = getUrlSegments(url);
    return parts[parts.length - 1];
};

var getUrlSegments = exports.getUrlSegments = function(url) {
    var pathname = Url.parse(url || window.location.href, false).pathname;

    if (endsWith(pathname, '/')) {
        pathname = pathname.substring(0, pathname.length - 1);
    }

    return pathname.split('/');
};

exports.removeLastUrlSegment = function(url) {
    var updatedurl = Url.parse(url || window.location.href, false);
    var segs = getUrlSegments(url);
    segs.pop();

    updatedurl.pathname = segs.join('/');

    if (updatedurl.pathname[updatedurl.pathname.length - 1] != '/') {
        updatedurl.pathname += '/';
    }

    return Url.format(updatedurl);
};

exports.appendSegmentToUrl = function (segment, inputurl) {
    var url = Url.parse(inputurl || window.location.href, false);
    var segs = getUrlSegments(inputurl);

    segs.push(segment);

    url.pathname = segs.join('/');

    return Url.format(url);
};

exports.pushState = function (url) {
    if (history.pushState) {
        history.pushState({}, '', url);
    } else {
        window.location = url;
    }
};

var parseQueryString = exports.parseQueryString = function () {
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

exports.getCurrentFilterString = function() {
    return parseQueryString().q || '{}';
};

exports.$find = function (selector, $parent) {
    // Find 'selector' via JQuery, inside $parent if specified.
    // Log to console if not found.
    var $el;
    if ($parent) {
        $el = $parent.find(selector);
    } else {
        $el = $(selector);
    }
    if ($el.length === 0) {
        if (window.console) {
            window.console.log('Selector not found: ' + selector);
        }
    }
    return $el;
};


exports.webMercatorToLatLng = function(x, y) {
    var originShift =  (2.0 * Math.PI * 6378137.0 / 2.0) / 180.0;
    var d2r = Math.PI / 180.0;
    var r2d = 180.0 / Math.PI;

    var lat = r2d * ((2.0 * Math.atan(Math.exp(d2r * y / originShift))) - Math.PI / 2.0);
    return {lat: lat, lng: x / originShift};

};

exports.lonLatToWebMercator = function(lon, lat) {
    var originShift = (2.0 * Math.PI * (6378137.0 / 2.0)) / 180.0;
    return {
        x: originShift * lon,
        y: originShift * (Math.log(Math.tan((90.0 + lat) * (Math.PI / 360.0)))) / (Math.PI / 180.0)
    };
};

var endsWith = exports.endsWith = function(str, ends) {
    if (ends === '') return true;
    if (str === null || ends === null) return false;

    return str.length >= ends.length &&
        str.slice(str.length - ends.length) === ends;
};
