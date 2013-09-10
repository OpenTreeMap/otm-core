"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs');

exports = module.exports = function (config) {

    var geocode = function (address, success, error) {
        return $.ajax({
            url: '/geocode',
            type: 'GET',
            data: {address: address},
            dataType: 'json',
            success: success,
            error: error
        });
    };

    return {
        geocode: geocode,  

        geocodeStream: function(addressStream) {
            return addressStream.flatMap(function (address) {
                return Bacon.fromPromise(geocode(address));
            });
        }
    };
};