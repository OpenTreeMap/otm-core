"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),
    geocoder = require('treemap/geocoder'),
    otmTypeahead = require('treemap/otmTypeahead');

module.exports = function (options) {
    var $addressInput = $(options.addressInput),
        geocodeCandidateStream = options.searchTriggerStream.map(function() {
            return otmTypeahead.getDatum($addressInput);
        }).filter('.magicKey'),
        gcoder = geocoder(options.config),
        geocodeResponseStream = gcoder.geocodeStream(geocodeCandidateStream);

    return geocodeResponseStream;
};
