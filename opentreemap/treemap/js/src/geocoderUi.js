"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    mustache = require('mustache');

module.exports = function (options) {
    var geocodeResponseStream = options.geocodeResponseStream,
        cancelGeocodeSuggestionStream = options.cancelGeocodeSuggestionStream,
        resultTemplate = options.resultTemplate,
        addressInput = options.addressInput,
        displayedResultsSelector = options.displayedResults,
        geocodeResultsTemplate = mustache.compile($(resultTemplate).html());

    // A stream of all geocode responses that have a single exact
    // match, converted to a standard result object
    var singleGeocodeMatchStream = geocodeResponseStream
        .filter(geocodeResponseHasASingleCandidate)
        .map(function (res) {
            var match = res.candidates[0];
            match.coordinates = [match.x,  match.y];
            return match;
        });

    // When there are multiple geocode results, show them to the user.
    geocodeResponseStream
        .filter(geocodeResponseHasMultipleCandidates)
        .onValue(showGeocodeCandidates, addressInput, geocodeResultsTemplate);

    // A stream of user-selected geocode responses from the popover.
    // The popover results are added to the page dynamically, so
    // set up a live-style selector.
    var resultChosenStream = $("body").asEventStream('click', displayedResultsSelector,
        function (e, args) {
            var $result = $(e.target);
            return {
                x: $result.data('x'),
                y: $result.data('y'),
                coordinates: [$result.data('x'),  $result.data('y')],
                address: $result.data('address')
            };
        });

    // Connect geocode cancel events to destroying the suggestion popover
    cancelGeocodeSuggestionStream
        .merge(resultChosenStream)
        .onValue(function () {
            $(addressInput).popover('hide').popover('destroy');
        });

    // Return a stream of geocoded locations (one for each resolved search)
    return singleGeocodeMatchStream.merge(resultChosenStream);
};

// Display a list of geocode candidates as a popover under the search text box.
function showGeocodeCandidates(addressInput, template, res) {
    if (res.candidates) {
        $(addressInput).popover({
            html: true, // Allows 'content' to be markup
            content: template(res),
            placement: 'bottom',
            trigger: 'manual',
            title: 'Results'
        }).popover('show');
    } else {
        window.alert('There was a problem running your search.');
    }
}

function geocodeResponseHasASingleCandidate(res) {
    return res && res.candidates && res.candidates.length === 1;
}

function geocodeResponseHasMultipleCandidates(res) {
    return res && res.candidates && res.candidates.length > 1;
}
