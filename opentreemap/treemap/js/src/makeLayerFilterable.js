"use strict";

var _ = require("underscore");

function filterObjectIsEmpty(o) {
    if (o) {
        return _.keys(o).length === 0;
    } else {
        return true;
    }
}

function uriEncodeFilterObject(o) {
    return encodeURIComponent(JSON.stringify(o));
}

var _urlTemplate = _.template('<%= originalUrl %>&<%= filterQueryArgumentName %>=<%= uriEncodedFilterObject %>');

function makeFilterUrl(originalUrl, filterQueryArgumentName, filter) {
    return _urlTemplate({
        originalUrl: originalUrl,
        filterQueryArgumentName: filterQueryArgumentName,
        uriEncodedFilterObject: uriEncodeFilterObject(filter)
    });
}

function makeLayerFilterable(layer, originalUrl, filterQueryArgumentName) {
    layer.clearFilter = function() {
        layer.setUrl(originalUrl);
    };

    layer.setFilter = function(filter) {
        if (filterObjectIsEmpty(filter)) {
            layer.clearFilter();
        } else {
            if (_.isArray(originalUrl)) {
                layer.setUrl(_.reduce(originalUrl,
                    function (urls, url) {
                        urls.push(makeFilterUrl(
                            url, filterQueryArgumentName, filter));
                        return urls;
                    }, []));
            } else {
                layer.setUrl(makeFilterUrl(originalUrl,
                    filterQueryArgumentName, filter));
            }
        }
    };

    layer.setUnfilteredUrl = function (url) {
        originalUrl = url;
        layer.setUrl(url);
    };

    return layer;
}

module.exports = makeLayerFilterable;
