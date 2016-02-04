"use strict";

var $ = require('jquery'),
    U = require('treemap/utility'),
    _ = require('lodash'),
    Bacon = require('baconjs');

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

exports = module.exports = function (config) {

    var geocodeServer = function (address, magicKey) {
        var data = {
            address: address,
            key: magicKey
        };
        if (config.instance && config.instance.extent) {
            _.extend(data, config.instance.extent);
        }
        return Bacon.fromPromise(
            $.ajax({
                url: '/geocode',
                type: 'GET',
                data: data,
                dataType: 'json'
            }));
    };

    var reverseGeocodeClient = function(latLng, distance) {
        var url = '//geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode';
        var params = {
            'location': latLngToParam(latLng),
            'distance': distance,
            'outSR': '3857', // Returning web mercator given latlng is a helpful side-effect
            'f': 'json'
        };

        return Bacon.fromPromise(
            $.ajax({
                url: url,
                type: 'GET',
                data: params,
                crossDomain: true,
                dataType: 'jsonp'
            }));
    };


    return {
        geocodeStream: function(datumStream) {
            return datumStream.flatMap(function (datum) {
                return geocodeServer(datum.text, datum.magicKey);
            }).flatMap(function(response) {
                if (response.candidates && response.candidates.length > 0) {
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
