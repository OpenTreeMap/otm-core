"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    U = require('./utility'),
    csrf = require('./csrf'),

    mapManager = require('./mapManager'),
    Search = require('./search'),
    otmTypeahead = require('./otmTypeahead'),
    modes = require('./modeManagerForMapPage'),

    isEnterKey = require('./baconUtils').isEnterKey;


var app = {
    initTypeAheads: function(config) {
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
    },

    resetEventStream: function() {
        return $("#search-reset").asEventStream("click");
    },

    searchEventStream: function() {
        var enterKeyPressStream = $('input[data-class="search"]')
                .asEventStream("keyup")
                .filter(isEnterKey),

            performSearchClickStream = $("#perform-search")
                .asEventStream("click"),

            triggerEventStream = enterKeyPressStream.merge(
                performSearchClickStream);

        return triggerEventStream;
    },

    redirectToSearchPage: function (config, query) {
        query = U.getUpdatedQueryString('q', JSON.stringify(query));

        window.location.href =
            config.instance.url + 'map/?' + query;
    }
};

module.exports = {
    init: function (config) {
        app.resetEventStream()
            .onValue(Search.reset);

        app.initTypeAheads(config);

        app.searchEventStream()
            .map(Search.buildSearch)
            .onValue(app.redirectToSearchPage, config);
    },

    initMapPage: function (config) {
        var map = mapManager.init(config),
            searchEventStream = app.searchEventStream(),
            resetStream = app.resetEventStream();

        // Set up cross-site forgery protection
        $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

        app.initTypeAheads(config);

        modes.init(config, map, mapManager.updateGeoRevHash);
        modes.activateBrowseTreesMode();

        $('.addBtn').click(modes.activateAddTreeMode);

        // Use a bus to delay sending the initial signal
        // seems like you could merge with Bacon.once(initialSearch)
        // but that empirically doesn't work

        // Don't duplicate queries
        var lastQuery = null;

        var triggerSearchFromUrl = new Bacon.Bus();
        var initialQueryBus = triggerSearchFromUrl.flatMap(function() {
            var query = U.parseQueryString().q || '{}';
            if (lastQuery != query) {
                lastQuery = query;
                return JSON.parse(query);
            } else {
                return Bacon.never();
            }
        });
        var triggeredQueryBus = resetStream.map({})
                                           .merge(initialQueryBus);

        window.addEventListener('popstate', function(event) {
            triggerSearchFromUrl.push({});
        }, false);

        var builtSearchEvents = searchEventStream
                .merge(resetStream)
                .map(Search.buildSearch)
                .merge(triggeredQueryBus);

        triggeredQueryBus.onValue(Search.applySearchToDom);

        Search.init(builtSearchEvents, config, mapManager.setFilter);

        builtSearchEvents
            .map(JSON.stringify)
            .map(function(q) {
                if (q == '{}') {
                    return null;
                } else {
                    return q;
                }
            })
            .map(U.getUpdateUrlByUpdatingQueryStringParam, 'q')
            .filter(function(url) {
                return url != window.location.href;
            })
            .onValue(U.pushState);

        triggerSearchFromUrl.push({});

    }
};
