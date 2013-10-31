"use strict";

var url = require('url'),
    QS = require('querystring'),
    $ = require('jquery'),
    L = require('leaflet'),
    console = require('console-browserify');

exports.getLastUrlSegment = function(urlString) {
    var parts = getUrlSegments(urlString);
    return parts[parts.length - 1];
};

var getUrlSegments = exports.getUrlSegments = function(inputUrl) {
    var pathname = url.parse(inputUrl || window.location.href, false).pathname;

    if (endsWith(pathname, '/')) {
        pathname = pathname.substring(0, pathname.length - 1);
    }

    return pathname.split('/');
};

exports.removeLastUrlSegment = function(inputUrl) {
    var updatedurl = url.parse(inputUrl || window.location.href, false);
    var segs = getUrlSegments(inputUrl);
    segs.pop();

    updatedurl.pathname = segs.join('/');

    if (updatedurl.pathname[updatedurl.pathname.length - 1] != '/') {
        updatedurl.pathname += '/';
    }

    return url.format(updatedurl);
};

exports.appendSegmentToUrl = function (segment, inputUrl, appendSlash) {
    var parsedUrl = url.parse(inputUrl || window.location.href, false);
    var segs = getUrlSegments(inputUrl);

    segs.push(segment);

    parsedUrl.pathname = segs.join('/');

    var formattedUrl = url.format(parsedUrl);

    if (appendSlash) {
        formattedUrl += '/';
    }

    return formattedUrl;
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
        console.warn('Selector not found: ' + selector);
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

exports.webMercatorToLeafletLatLng = function(x, y) {
    var latLng = exports.webMercatorToLatLng(x, y),
        leafletLatLng = L.latLng(latLng.lat, latLng.lng);
    return leafletLatLng;
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
