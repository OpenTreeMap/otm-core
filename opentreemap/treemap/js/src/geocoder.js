"use strict";

var $ = require('jquery'),
    _ = require('underscore'),
    Bacon = require('baconjs');

exports = module.exports = function (config) {

    var geocode = function (address, bbox, success, error) {
        return $.ajax({
            url: '/geocode',
            type: 'GET',
            data: _.extend({address: address}, bbox),
            dataType: 'json',
            success: success,
            error: error
        });
    };

    return {
        geocodeStream: function(addressStream) {
            return addressStream.flatMap(function (address) {
                return Bacon.fromPromise(geocode(address, config.instance.extent));
            });
        }
    };
};
