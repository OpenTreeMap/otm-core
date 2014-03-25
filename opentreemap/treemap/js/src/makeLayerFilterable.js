"use strict";

var _ = require("lodash");

function filtersAreEmpty(o) {
    var filterEmpty = o.filters ? _.keys(o).length === 0 : true;
    var displayEmpty = _.isUndefined(o.display) || _.isNull(o.display);
    return filterEmpty && displayEmpty;
}

function uriEncodeObject(o) {
    return encodeURIComponent(JSON.stringify(o));
}

var _urlTemplate = _.template('<%= originalUrl %>' +
        '&<%= filterQueryArgumentName %>=<%= uriEncodedFilterObject %>' +
        '&<%= displayQueryArgumentName %>=<%= uriEncodedDisplayList %>');

function makeFilterUrl(originalUrl, filterQueryArgumentName, displayQueryArgumentName, filters) {
    return _urlTemplate({
        originalUrl: originalUrl,
        filterQueryArgumentName: filterQueryArgumentName,
        displayQueryArgumentName: displayQueryArgumentName,
        uriEncodedDisplayList: uriEncodeObject(filters.display),
        uriEncodedFilterObject: uriEncodeObject(filters.filter)
    });
}

function makeLayerFilterable(layer, originalUrl, filterQueryArgumentName, displayQueryArgumentName) {
    layer.clearFilter = function() {
        layer.setUrl(originalUrl);
    };

    layer.setFilter = function(filters) {
        if (filtersAreEmpty(filters)) {
            layer.clearFilter();
        } else {
            if (_.isArray(originalUrl)) {
                layer.setUrl(_.reduce(originalUrl,
                    function (urls, url) {
                        urls.push(makeFilterUrl(
                            url, filterQueryArgumentName, displayQueryArgumentName, filters));
                        return urls;
                    }, []));
            } else {
                layer.setUrl(makeFilterUrl(originalUrl,
                    filterQueryArgumentName, displayQueryArgumentName, filters));
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
