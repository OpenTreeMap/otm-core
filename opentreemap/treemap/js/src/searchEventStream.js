"use strict";

// Given a set of search input elements (text boxes) and a "search" button,
// Return a stream of "search" events triggered by hitting "Enter" in one of
// the input boxes or clicking the "search" button.

var $ = require('jquery'),
    Bacon = require('baconjs'),
    BU = require('./baconUtils');

module.exports = function(options) {
    var searchInputs = $(options.searchInputs),
        searchButton = $(options.searchButton),
        enterKeyPressStream = searchInputs
            .asEventStream("keyup")
            .filter(BU.isEnterKey),

        performSearchClickStream = searchButton.asEventStream("click"),

        triggerEventStream = enterKeyPressStream.merge(
            performSearchClickStream);

    return triggerEventStream;
};
