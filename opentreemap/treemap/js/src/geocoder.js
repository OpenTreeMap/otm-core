"use strict";

var $ = require('jquery'),
    U = require('utility'),
    _ = require('underscore'),
    Bacon = require('baconjs');

exports = module.exports = function (config) {

    var geocodeServer = function (address, bbox, success, error) {
        return Bacon.fromPromise(
            $.ajax({
                url: '/geocode',
                type: 'GET',
                data: _.extend({address: address}, bbox),
                dataType: 'json',
                success: success,
                error: error
            }));
    };

    // This uses filters similar to:
    // https://github.com/azavea/python-omgeo/blob/master/omgeo/services/__init__.py
    var processGeocoderResponse = function(geocoderResponse) {
        function groupByAndExtractMaxScore(chained, param) {
            return chained.groupBy(param)
                .values()
                .map(function(candidateGroup) {
                    return _.max(candidateGroup, function(candidate) {
                        return candidate.score;
                    });
                });
        }

        // Extract geom (x,y), score, name, and type
        var candidates = _.chain(geocoderResponse.locations)
            .map(function(candidate) {
                var xy = U.lonLatToWebMercator(
                    candidate.feature.geometry.x,
                    candidate.feature.geometry.y);

                return {
                    x: xy.x,
                    y: xy.y,
                    loc: 'x:' + xy.x + ',y:' + xy.y,
                    srid: '3857',
                    score: candidate.feature.attributes.Score,
                    type: candidate.feature.attributes.Addr_Type,
                    address: candidate.name
                };
            });

        // Only care about scores that are in the following
        // list, in order of desirability
        var supportedTypes = ['PointAddress', 'StreetAddress',
                              'StreetName'];

        candidates = candidates.filter(function(candidate) {
            return _.contains(supportedTypes, candidate.type);
        });

        // Remove duplicates based on location and name
        candidates = groupByAndExtractMaxScore(candidates, 'loc');
        candidates = groupByAndExtractMaxScore(candidates, 'address');

        // Remove scores less than 'threshold'
        candidates = candidates.filter(function(candidate) {
            return candidate.score >= config.geocoder.threshold;
        });

        // Only accept types types
        var types = candidates
                .groupBy('type')
                .map(function(list, type) {
                    return [type, _.sortBy(list, 'score')];
                })
                .object()
                .value();

        // Construct candidate list based on supportedType's order
        var filteredCandidates = _.chain(supportedTypes)
                .map(function(type) { return types[type] || []; })
                .flatten()
                .value();

        return { candidates: filteredCandidates };
    };

    var filterBbox = function(bbox, response) {
        if (response.candidates) {
            response.candidates = _.filter(
                response.candidates, function(candidate) {
                    return candidate.x >= bbox.xmin &&
                        candidate.x <= bbox.xmax &&
                        candidate.y >= bbox.ymin &&
                        candidate.y <= bbox.ymax;
                });
        }

        return response;
    };

    var geocodeClient = function(address, box) {
        var url = '//geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/find';
        var params = {
            'maxLocations': config.geocoder.maxLocations,
            'outFields': 'Loc_name,Score,Addr_Type,DisplayX,DisplayY',
            'f': 'json',
            text: address
        };

        return Bacon.fromPromise(
            $.ajax({
                url: url,
                type: 'GET',
                data: params,
                crossDomain: true,
                dataType: 'jsonp'
            }))
            .map(processGeocoderResponse)
            .map(filterBbox, box);
    };

    return {
        geocodeStream: function(addressStream) {
            return addressStream.flatMap(function (address) {
                return geocodeClient(address, config.instance.extent);
            }).flatMap(function(response) {
                if (response.candidates && response.candidates.length > 0) {
                    return Bacon.once(response);
                } else {
                    return Bacon.once(
                        new Bacon.Error(config.geocoder.errorString));
                }
            });
        }
    };
};
