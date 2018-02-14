"use strict";

var url = require('url'),
    QS = require('querystring'),
    $ = require('jquery'),
    L = require('leaflet'),
    _ = require('lodash'),
    console = require('console-browserify');

exports.getUpdatedQueryString = function (k, v) {
    var parsedUrl = url.parse(window.location.href, true);
    var query = parsedUrl.query || {};

    query[k] = v;

    return QS.stringify(query);
};

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

exports.offsetLatLngByMeters = function(latLng, dx, dy) {
    // Approximation formulas from http://stackoverflow.com/a/19356480/362702
    var lat = latLng.lat,
        lng = latLng.lng,
        latRad = lat * Math.PI / 180,
        m_per_deg_lat = 111132.954 - 559.822 * Math.cos(2 * latRad) + 1.175 * Math.cos(4 * latRad),
        m_per_deg_lng = (Math.PI / 180) * 6367449 * Math.cos(latRad),
        newLat = lat + dy / m_per_deg_lat,
        newLng = lng + dx / m_per_deg_lng;
    return { lat: newLat, lng: newLng };
};

exports.makeZoomLatLngQuery = function(zoomLatLng) {
    var zoom = zoomLatLng.zoom,
        precision = Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2)),
        lat = zoomLatLng.lat.toFixed(precision),
        lng = zoomLatLng.lng.toFixed(precision),
        query = [zoom, lat, lng].join('/');
    return query;
};

// TODO: Respect instance units configuration.
// https://github.com/OpenTreeMap/otm-addons/issues/326
exports.getPolygonDisplayArea = function(poly) {
    function totalAreaInMeters(collection) {
        if (_.isArray(collection[0])) {
            return _(collection)
                    .map(totalAreaInMeters)
                    .reduce(function(sum, num) {
                        return sum + num;
                    });
        } else {
            return L.GeometryUtil.geodesicArea(collection);
        }
    }

    var areaSqMeters = totalAreaInMeters(poly.getLatLngs()),
        areaSqFeet = areaSqMeters * 10.7639;
    return areaSqFeet;
};

var endsWith = exports.endsWith = function(str, ends) {
    if (ends === '') return true;
    if (str === null || ends === null) return false;

    return str.length >= ends.length &&
        str.slice(str.length - ends.length) === ends;
};

// Takes a set of functions and returns a fn that is the juxtaposition
// of those fns. The returned fn takes a variable number of args, and
// returns a vector containing the result of applying each fn to the
// args (left-to-right).
exports.juxt = function(fns) {
    return function (val) {
        return _.map(fns, function (fn) { return fn(val); });
    };
};


exports.warnDeprecatedErrorMessage = function (errorObject) {
    console.log('returning "error" as a key from an ' +
                'endpoint is deprecated. Please use ' +
                '"globalErrors" or "fieldErrors"');
    console.log(errorObject);
};

// http://stackoverflow.com/a/24922761/362702
exports.exportToCsv = function (rows, filename) {
    var processRow = function (row) {
        var finalVal = '';
        for (var j = 0; j < row.length; j++) {
            var innerValue = row[j] === null ? '' : row[j].toString();
            if (row[j] instanceof Date) {
                innerValue = row[j].toLocaleString();
            }
            var result = innerValue.replace(/"/g, '""');
            if (result.search(/("|,|\n)/g) >= 0)
                result = '"' + result + '"';
            if (j > 0)
                finalVal += ',';
            finalVal += result;
        }
        return finalVal + '\n';
    };

    var csvFile = '';
    for (var i = 0; i < rows.length; i++) {
        csvFile += processRow(rows[i]);
    }

    var blob = new Blob([csvFile], { type: 'text/csv;charset=utf-8;' });
    if (navigator.msSaveBlob) { // IE 10+
        navigator.msSaveBlob(blob, filename);
    } else {
        var link = document.createElement("a");
        if (link.download !== undefined) { // feature detection
            // Browsers that support HTML5 download attribute
            var url = window.URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } else {
            var csvContent = "data:text/csv;charset=utf-8;\n" + csvFile,
                uri = encodeURI(csvContent);
            window.open(uri);
        }
    }
};

exports.modalsFocusOnFirstInputWhenShown = function () {
    $('.modal').on('shown.bs.modal', function() {
        $(this).find('input').first().trigger('focus').trigger('select');
    });
};
