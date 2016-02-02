"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    geocoder = require('treemap/geocoder'),
    otmTypeahead = require('treemap/otmTypeahead');

module.exports = function (options) {
    var $addressInput = $(options.addressInput),
        geocodeCandidateStream = options.searchTriggerStream
            .map(getDatum)
            .filter(_.identity),  // ignore false values
        gcoder = geocoder(options.config),
        geocodeResponseStream = gcoder.geocodeStream(geocodeCandidateStream);

    return geocodeResponseStream;

    function getDatum() {
        var datum = otmTypeahead.getDatum($addressInput),
            inputText = $addressInput.val();
        if (datum) {
            if (datum.text) {
                if (datum.text.startsWith(inputText)) {
                    // A suggested address was chosen, so use it (with its magic key)
                    return datum;
                }
            } else {
                // Datum is not an address for searching (it's e.g. a boundary)
                return false;
            }
        }
        if (inputText) {
            // Suggestion was not chosen or is stale, so use what the user typed
            return {text: inputText};
        }
    }
};
