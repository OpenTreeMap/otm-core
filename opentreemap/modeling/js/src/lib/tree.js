"use strict";

var _ = require('lodash'),
    F = require('modeling/lib/func.js'),
    Location = require('modeling/lib/location.js');

var id = 0;

// Represents an individual tree or a tree distribution.
function Tree(options) {
    options = _.defaults({}, options, {
        uid: id++,
        type: 'single',
        diameter: 2,
        quantity: 1,
        species: '',
        locations: null
    });

    function isSingleTree() {
        return options.type === 'single';
    }

    function isDistribution() {
        return options.type === 'distribution';
    }

    function quantity() {
        return isSingleTree() ?
            options.locations && options.locations.length || 0 :
            options.quantity;
    }

    function serialize() {
        return isSingleTree() ?
            serializeSingleTree() : serializeDistribution();
    }

    function serializeSingleTree() {
        var locations = _.invokeMap(options.locations, 'serialize');
        return {
            species: options.species,
            diameter: options.diameter,
            count: locations.length,
            locations: locations
        };
    }

    function serializeDistribution() {
        return {
            species: options.species,
            diameter: options.diameter,
            count: options.quantity
        };
    }

    function clone(cloneOptions) {
        return new Tree(_.defaults({}, cloneOptions, options));
    }

    function equals(other) {
        var locationsMatch =
            options.locations.length === other.locations().length &&
            // Assumes locations are sorted the same way on both objects.
            _.every(
                _.zip(options.locations, other.locations()),
                F.expandArguments(function(loc, otherLoc) {
                    return loc.equals(otherLoc);
                })
            );
        return other.uid() === options.uid &&
               other.diameter() === options.diameter &&
               other.species() === options.species &&
               other.quantity() === quantity() &&
               locationsMatch;
    }

    return {
        uid: F.getter(options.uid),
        type: F.getter(options.type),
        diameter: F.getter(options.diameter),
        species: F.getter(options.species),
        locations: F.getter(options.locations || []),
        quantity: quantity,
        isSingleTree: isSingleTree,
        isDistribution: isDistribution,
        serialize: serialize,
        clone: clone,
        equals: equals
    };
}
Tree.deserialize = function(data) {
    function deserializeSingleTree() {
        var uid = id++;
        return new Tree({
            uid: uid,
            type: 'single',
            species: data.species,
            diameter: data.diameter,
            locations: _.map(data.locations, function(locData) {
                return  Location.deserialize(_.defaults(locData, {
                    treeUid: uid
                }));
            })
        });
    }

    function deserializeDistribution() {
        return new Tree({
            type: 'distribution',
            species: data.species,
            diameter: data.diameter,
            quantity: data.count
        });
    }

    return data.locations ? deserializeSingleTree() : deserializeDistribution();
};

module.exports = Tree;
