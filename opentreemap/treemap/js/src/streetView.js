"use strict";

var google = require('googlemaps'),
    $ = require('jquery'),
    _ = require('lodash'),

    utility = require('treemap/utility');

exports.create = function(options) {
    var panorama = null,
        curLocation = null,
        showAddress = !options.hideAddress;

    var div = options.streetViewElem;

    function update(location) {
        if (_.isEqual(curLocation, location)) {
            return;
        }
        curLocation = location;

        var latlng;
        if (location.lat && location.lng) {
            latlng = location;
        } else {
            latlng = utility.webMercatorToLatLng(location.x, location.y);
        }

        var pos = new google.maps.LatLng(latlng.lat, latlng.lng);
        new google.maps.StreetViewService().getPanoramaByLocation(pos, 50, function(data, status) {
            if (status == google.maps.StreetViewStatus.OK) {
                if (panorama === null) {
                    panorama = new google.maps.StreetViewPanorama(div, {
                        position:pos,
                        addressControl: showAddress,
                        panControl: false,
                    });
                } else {
                    panorama.setPosition(pos);
                }
            }
            else {
                panorama = null;
                $(div).html(options.noStreetViewText || '');
            }
        });
    }
    update(options.location);

    return {
        update: update
    };
};
