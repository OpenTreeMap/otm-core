"use strict";

// Given a set of search input elements (text boxes) and a "search" button,
// Return a stream of "search" events triggered by hitting "Enter" in one of
// the input boxes or clicking the "search" button.

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    otmTypeahead = require('treemap/otmTypeahead'),
    U = require('treemap/utility'),
    Search = require('treemap/search'),
    BU = require('treemap/baconUtils');

// Placed onto the jquery object
require('bootstrap-datepicker');

module.exports = exports = {
    initSearchUi: function(config) {
        var $advancedToggle = $("#search-advanced"),
            $advancedPane = $("#advanced-search-pane");
        otmTypeahead.create({
            name: "species",
            url: config.instance.url + "species/",
            input: "#species-typeahead",
            template: "#species-element-template",
            hidden: "#search-species",
            button: "#species-toggle",
            reverse: "id",
            forceMatch: true
        });
        otmTypeahead.create({
            name: "boundaries",
            url: config.instance.url + "boundaries/",
            input: "#boundary-typeahead",
            template: "#boundary-element-template",
            hidden: "#boundary",
            button: "#boundary-toggle",
            reverse: "id"
        });
        $advancedToggle.on("click", function() {
            $advancedPane.toggle(0); // Show/hide with 0 animation time
        });
        $advancedPane.find("input[data-date-format]").datepicker();
    },

    resetEventStream: function() {
        return $("#search-reset").asEventStream("click");
    },

    searchEventStream: function() {
        return BU.enterOrClickEventStream({
            inputs: 'input[data-class="search"]',
            button: '#perform-search'
        });
    },

    redirectToSearchPage: function (config, query) {
        query = U.getUpdatedQueryString('q', JSON.stringify(query));

        window.location.href =
            config.instance.url + 'map/?' + query;
    },

    getElems: _.partial(Search.buildElems, '[data-search-type]'),

    init: function (config) {
        var elems = exports.getElems();

        exports.resetEventStream()
               .onValue(Search.reset, elems);

        exports.initSearchUi(config);

        exports.searchEventStream()
           .map(Search.buildSearch, elems)
           .onValue(exports.redirectToSearchPage, config);
    }
};
