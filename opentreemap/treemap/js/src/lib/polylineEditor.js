"use strict";

var L = require('leaflet'),
    _ = require('lodash'),
    U = require('treemap/lib/utility.js'),
    config = require('treemap/lib/config.js');

require('leaflet-draw');

function makePolygonFromPoint(p1) {
    var p2 = U.offsetLatLngByMeters(p1, -20, -20);

    return[
        [p1.lng, p1.lat],
        [p2.lng, p1.lat],
        [p2.lng, p2.lat],
        [p1.lng, p2.lat]
    ];
}

function flipXY(coordinates) {
    return _.map(coordinates, function (pair) {
        return [pair[1], pair[0]];
    });
}

module.exports = function (options) {
    var areaPolygon,
        points;

    return {

        mapManager: options.mapManager,

        initAreaPolygon: function(options) {
            if ((options.points && options.plotMarker) ||
                (!options.points && !options.plotMarker)) {
                throw("must provide points or plotMarker as option");
            } else if (options.points) {
                points = options.points;
            } else {
                points = makePolygonFromPoint(options.plotMarker.getLatLng());
            }
            areaPolygon = new L.Polygon(flipXY(points));
            areaPolygon.addTo(this.mapManager.map);
        },

        getPoints: function () {
            if (!areaPolygon) {
                return null;
            }
            var points = _.map(areaPolygon.getLatLngs()[0], function (point) {
                return [point.lng, point.lat];
            });
            points.push(points[0]);
            return points;
        },

        hasMoved: function(points1) {
            var points2 = this.getPoints();
            if (_.isNull(points2)) {
                return false;
            } else {
                var pairPairs = _.zip(points1, points2);
                return !_.every(pairPairs, function(pairPair) {
                    var pair1 = pairPair[0],
                        pair2 = pairPair[1];
                    return pair1[0] === pair2[0] && pair1[1] === pair2[1];
                });
            }
        },

        removeAreaPolygon: function() {
            if (areaPolygon) {
                this.disableAreaPolygon();
                this.mapManager.map.removeLayer(areaPolygon);
                areaPolygon = null;
            }
        },

        enableAreaPolygon: function(options) {
            if (!areaPolygon) {
                this.initAreaPolygon(options);
            }
            areaPolygon.editing.enable();
        },

        disableAreaPolygon: function() {
            if (areaPolygon) {
                areaPolygon.editing.disable();
            }
        }
    };
};
