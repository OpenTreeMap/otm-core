"use strict";

var google = require('googlemaps'),
    $ = require('jquery'),
    _ = require('underscore'),

    utility = require('treemap/utility');

exports.create = function(options) {
    var panorama = null,
        curLocation = null;

    var div = options.streetViewElem;

    function update(location) {
        if (_.isEqual(curLocation, location)) {
            return;
        }
        curLocation = location;

        var latlng = utility.webMercatorToLatLng(location.x, location.y);
        var pos = new google.maps.LatLng(latlng.lat, latlng.lng);
        new google.maps.StreetViewService().getPanoramaByLocation(pos, 50, function(data, status) {
            if (status == google.maps.StreetViewStatus.OK) {
                if (panorama === null) {
                    panorama = new google.maps.StreetViewPanorama(div, {position:pos, addressControl: true});
                } else {
                    panorama.setPosition(pos);
                }
            }
            else {
                $(div).html(options.noStreetViewText);
            }
        });
    }
    update(options.location);

    return {
        update: update
    };
};
