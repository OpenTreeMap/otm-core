"use strict";

var OL = require("OpenLayers"),
    _ = require("underscore");

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

var _urlTemplate = _.template('<%= originalUrl %>?<%= filterQueryArgumentName %>=<%= uriEncodedFilterObject %>');

OL.Layer.OTM = OL.Layer.OTM || OL.Class(OL.Layer.XYZ, {
    originalUrl: null,
    filter: null,
    filterQueryArgumentName: null,

    initialize: function(name, url, options) {
        var newArgs;
        options = OL.Util.applyDefaults({
                sphericalMercator: true,
                url: url
            }, options);
        newArgs = [name, null, options];
        OL.Layer.XYZ.prototype.initialize.apply(this, newArgs);
        this.url = url;
        this.originalUrl = url;
        this.filterQueryArgumentName = options.filterQueryArgumentName;
    },

    clearFilter: function() {
        this.filter = undefined;
        this.url = this.originalUrl;
        this.redraw();
    },

    setFilter: function(filter) {
        if (filterObjectIsEmpty(filter)) {
            this.clearFilter();
        } else {
            this.filter = filter;
            this.url = _urlTemplate({
                originalUrl: this.originalUrl,
                filterQueryArgumentName: this.filterQueryArgumentName,
                uriEncodedFilterObject: uriEncodeFilterObject(filter)
            });
            this.redraw();
        }
    }
});
