"use strict";

var _ = require('lodash'),
    L = require('leaflet'),
    F = require('modeling/lib/func.js');

var id = 0;

// Represents an individual tree location on the map.
function Location(options) {
    options = _.defaults({}, options, {
        uid: id++
    });

    function getLatLng() {
        return new L.LatLng(options.lat, options.lng);
    }

    function serialize() {
        return {
            uid: options.uid,
            lat: options.lat,
            lng: options.lng
        };
    }

    function clone(cloneOptions) {
        return new Location(_.defaults({}, cloneOptions, options));
    }

    function equals(other) {
        return other.uid() === options.uid &&
               other.lat() === options.lat &&
               other.lng() === options.lng;
    }

    return {
        uid: F.getter(options.uid),
        treeUid: F.getter(options.treeUid),
        lat: F.getter(options.lat),
        lng: F.getter(options.lng),
        getLatLng: getLatLng,
        serialize: serialize,
        clone: clone,
        equals: equals
    };
}
Location.deserialize = function(data) {
    return new Location({
        treeUid: data.treeUid,
        lat: data.lat,
        lng: data.lng
    });
};

module.exports = Location;
