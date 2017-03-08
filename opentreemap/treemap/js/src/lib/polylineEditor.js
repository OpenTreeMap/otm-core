"use strict";

var L = require('leaflet'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    U = require('treemap/lib/utility.js'),
    numeral = require('numeral'),
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

function showArea(area, areaBus) {
    var displayArea = numeral(area).format('0,0');
    areaBus.push(displayArea);
}

module.exports = function (options) {
    var mapManager = options.mapManager,
        map = mapManager.map,
        areaPolygon,
        points,
        initialArea,
        areaBus = new Bacon.Bus();

    return {

        initAreaPolygon: function(options) {
            if ((options.points && options.plotMarker) ||
                (!options.points && !options.plotMarker)) {
                throw("must provide points or plotMarker as option");
            } else if (options.points) {
                points = options.points;
            } else {
                points = makePolygonFromPoint(options.plotMarker.getLatLng());
            }
            mapManager.customizeVertexIcons();
            areaPolygon = new L.Polygon(flipXY(points));
            areaPolygon.addTo(map);
            initialArea = U.getPolygonDisplayArea(areaPolygon);
            showArea(initialArea, areaBus);
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

        removeAreaPolygon: function(revertArea) {
            if (areaPolygon) {
                this.disableAreaPolygon();
                map.removeLayer(areaPolygon);
                if (revertArea) {
                    showArea(initialArea, areaBus);
                }
                areaPolygon = null;
            }
        },

        enableAreaPolygon: function(options) {
            if (!areaPolygon) {
                this.initAreaPolygon(options);
            }
            areaPolygon.editing.enable();

            map.on('draw:editvertex', function () {
                var area = U.getPolygonDisplayArea(areaPolygon);
                showArea(area, areaBus);
            });
        },

        disableAreaPolygon: function() {
            if (areaPolygon) {
                areaPolygon.editing.disable();
                map.off('draw:editvertex');
            }
        },

        areaStream: areaBus.map(_.identity)
    };
};
