"use strict";

var _ = require("lodash"),
    Search = require("treemap/search");

function filtersAreEmpty(o) {
    return Search.filterObjectIsEmpty(o.filter) && Search.displayListIsEmpty(o.display);
}

function makeFilterUrl(config, originalUrl, filters) {
    var query = Search.makeQueryStringFromFilters(config, filters);
    return originalUrl + (query ? '&' + query : '');
}

function makeLayerFilterable(layer, originalUrl, config) {
    layer.clearFilter = function() {
        layer.setUrl(originalUrl);
    };

    layer.setFilter = function(filters) {
        if (filtersAreEmpty(filters)) {
            layer.clearFilter();
        } else {
            if (_.isArray(originalUrl)) {
                layer.setUrl(_.map(originalUrl, function(url) {
                    makeFilterUrl(config, url, filters);
                }));
            } else {
                layer.setUrl(makeFilterUrl(config, originalUrl, filters));
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
