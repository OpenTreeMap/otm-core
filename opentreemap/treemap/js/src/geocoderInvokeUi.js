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
            if (datum.magicKey) {
                // Datum is an address suggestion
                if (datum.text.startsWith(inputText)) {
                    // Geocode this suggestion (using its magic key)
                    return datum;
                }
                // else user has edited the suggestion; fall through
            } else {
                // Datum is a boundary
                if (datum.value === inputText) {
                    // We don't geocode boundaries
                    return false;
                }
                // else user has edited the value; fall through
            }
        }
        if (inputText) {
            // The user either didn't choose a suggestion, or else chose
            // a selection and then edited it. Geocode what the user typed.
            return {text: inputText};
        } else {
            // No input text; don't geocode.
            return false;
        }
    }
};
