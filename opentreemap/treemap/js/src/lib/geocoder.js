"use strict";

var $ = require('jquery'),
    config = require('treemap/lib/config.js'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    reverse = require('reverse');

// ``coordToLatLng`` converts a 2d coordinate array or an object
// to an object with ``lat`` and ``lng`` values.
function coordToLatLngObject(latLng) {
    var lat, lng;
    if (_.isArray(latLng)) {
        lat = latLng[0];
        lng = latLng[1];
    } else {
        if (latLng.lat) { lat = latLng.lat; }
        if (latLng.lng) { lng = latLng.lng; }
        if (latLng.lon) { lng = latLng.lon; }
        if (latLng.x) { lng = latLng.x; }
        if (latLng.y) { lat = latLng.y; }
    }
    return {
        lat: lat,
        lng: lng
    };
}

// ``latLngToParam`` converts an object with ``lat`` and ``lng``
// values to a string suitable to be passed as a ``location`` query
// string argument to the ESRI reverse geocoder REST service
function latLngToParam(latLng) {
    return latLng.lng + ', ' + latLng.lat;
}

exports = module.exports = function () {
    var geocodeServer = function (address, magicKey, forStorage) {
        var data = {
            address: address,
            key: magicKey
        };
        if (forStorage) {
            data.forStorage = true;
        }
        if (config.instance && config.instance.extent) {
            _.extend(data, config.instance.extent);
        }
        return Bacon.fromPromise(
            $.ajax({
                url: reverse.geocode(),
                type: 'GET',
                data: data,
                dataType: 'json'
            }));
    };

    var token = null;
    var reverseGeocodeClient = function(latLng, distance) {
        var url = '//geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode';
        var params = {
            'location': latLngToParam(latLng),
            'distance': distance,
            'outSR': '3857', // Returning web mercator given latlng is a helpful side-effect
            'f': 'json',
            'forStorage': 'true',
        };
        var opts = {
            url: url,
            type: 'GET',
            data: params,
            crossDomain: true,
            dataType: 'jsonp'
        };

        if (token !== null) {
            opts.data.token = token;
            return Bacon.fromPromise($.ajax(opts));
        } else {
            return Bacon.fromPromise(
                $.getJSON(reverse.get_geocode_token())
                    .then(function(response) {
                        token = response.token;
                        opts.data.token = token;

                        return $.ajax(opts);
                    })
                    .fail(function() {
                        token = null;
                    })
            );
        }

        return Bacon.fromPromise(
            $.ajax());
    };


    return {
        geocodeStream: function(datumStream, forStorage) {
            return datumStream.flatMap(function (datum) {
                return geocodeServer(datum.text, datum.magicKey, forStorage);
            }).flatMap(function(response) {
                if (response.lat && response.lng) {
                    return Bacon.once(response);
                } else {
                    return Bacon.once(
                        new Bacon.Error(config.geocoder.errorString));
                }
            });
        },

        reverseGeocodeStream: function(coordStream) {
            return coordStream.map(coordToLatLngObject).flatMap(function (latLng) {
                return reverseGeocodeClient(latLng, config.reverseGeocodeDistance || 200);
            }).flatMap(function (response) {
                if (response && response.address) {
                    return Bacon.once(response);
                } else {
                    return Bacon.once(new Bacon.Error(
                        config.geocoder.reverseGeocoderErrorString));
                }
            });
        }
    };
};
