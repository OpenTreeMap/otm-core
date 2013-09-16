"use strict";

// Given a set of search input elements (text boxes) and a "search" button,
// Return a stream of "search" events triggered by hitting "Enter" in one of
// the input boxes or clicking the "search" button.

var $ = require('jquery'),
    _ = require('underscore'),
    Bacon = require('baconjs'),
    otmTypeahead = require('./otmTypeahead'),
    U = require('./utility'),
    Search = require('./search'),
    BU = require('./baconUtils');

module.exports = exports = {
    initSearchUi: function(config) {
        otmTypeahead.create({
            name: "species",
            url: config.instance.url + "species",
            input: "#species-typeahead",
            template: "#species-element-template",
            hidden: "#search-species",
            reverse: "id"
        });
        otmTypeahead.create({
            name: "boundaries",
            url: config.instance.url + "boundaries",
            input: "#boundary-typeahead",
            template: "#boundary-element-template",
            hidden: "#boundary",
            reverse: "id"
        });
        $("#search-advanced").on("click", function() {
            $("#advanced-search-pane").toggle(0); // Show/hide with 0 animation time
        });
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

        $('.addBtn').attr('href', config.instance.url + 'map/#addtree');
    }
};
