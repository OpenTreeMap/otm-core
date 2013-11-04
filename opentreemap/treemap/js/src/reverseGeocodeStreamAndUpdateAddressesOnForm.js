"use strict";

var geocoder = require('treemap/geocoder'),
    _ = require('underscore'),
    $ = require('jquery');

module.exports = function(config, triggerStream, formSelector) {
    var gcoder = geocoder(config);
    var reverseGeocodeStream = gcoder.reverseGeocodeStream(triggerStream);
    reverseGeocodeStream.onValue(function(geocode) {
        // Grab the applicaable values
        var updates = {'plot.address_street': geocode.address.Address,
                       'plot.address_city': geocode.address.City,
                       'plot.address_zip': geocode.address.Postal};

        // Apply the updates to the form
        var $form = $(formSelector);
        _.each(updates, function(value, key) {
            $form.find("input[name='" + key + "']").val(value);
        });
    });

    return reverseGeocodeStream;
};
