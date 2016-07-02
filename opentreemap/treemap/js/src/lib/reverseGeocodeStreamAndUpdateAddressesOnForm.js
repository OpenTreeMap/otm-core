"use strict";

var geocoder = require('treemap/lib/geocoder.js'),
    _ = require('lodash'),
    $ = require('jquery');

module.exports = function(triggerStream, formSelector) {
    var gcoder = geocoder();
    var reverseGeocodeStream = gcoder.reverseGeocodeStream(triggerStream);
    reverseGeocodeStream.onValue(function(geocode) {
        // Grab the applicable values
        var updates = {'address_street': geocode.address.Address,
                       'address_city': geocode.address.City,
                       'address_zip': geocode.address.Postal};

        // Apply the updates to the form. If key == "address_zip",
        // this will get the value for "plot.address_zip" or "garden.address_zip"
        var $form = $(formSelector);
        _.each(updates, function(value, key) {
            $form.find("input[name$='" + key + "']").val(value);
        });
    });

    return reverseGeocodeStream;
};
