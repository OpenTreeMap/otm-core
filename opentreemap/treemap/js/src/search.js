/* search.js */

//= require Bacon
//= require underscore

/*jslint nomen: true*/
/*globals $,_,OpenLayers,otm,document,Bacon,JSON*/
/*jslint indent: 4, white: true */

var Search = (function ($,Bacon,config) {
    "use strict";

    var exports = {},
        // Quite manual right now but should be nicer in the future
        elems = { '#search-species':
                  { 'key': 'species.id',
                    'pred': 'IS' },
                  '#dbh-min':
                  { 'key': 'tree.diameter',
                    'pred': 'MIN' },
                  '#boundary':
                  { 'key': 'plot.geom',
                    'pred': 'IN_BOUNDARY' },
                  '#dbh-max':
                  { 'key': 'tree.diameter',
                    'pred': 'MAX' }};

    function buildSearch(stream) {
        return _.reduce(elems, function(preds, key_and_pred, id) {
            var val = $(id).val(),
                pred = {};

            if (val && val.length > 0) {
                pred[key_and_pred.pred] = val;
                preds[key_and_pred.key] = pred;
            }

            return preds;
        }, {});
    }

    function executeSearch(search_query) {
        var search = $.ajax({
            url: '/' + config.instance.id + '/benefit/search',
            data: {'q': JSON.stringify(search_query)},
            type: 'GET',
            dataType: 'html'});

        return Bacon.fromPromise(search);
    }

    function displaySearch(result) {
        $("#search-results").html(result);
    }

    // Arguments
    //
    // triggerEventStream: a Bacon.js EventStream. The value
    //   of the item will be ignored and, instead, the current
    //   values of the search form fields will be scraped.
    //
    // plotLayer: An OpenLayers.Layer.OTM instance with the
    // `url` argument initialized to the unfiltered tile url.
    exports.init = function(triggerEventStream, plotLayer) {
        var searchStream = triggerEventStream.map(buildSearch);

        // binding is required to save the context of the plotLayer
        // `setFilter` instance method
        searchStream.onValue(_.bind(plotLayer.setFilter, plotLayer));

        searchStream
            .flatMap(executeSearch)
            .onValue(displaySearch);
    };

    return exports;

}($, Bacon, otm.settings));
