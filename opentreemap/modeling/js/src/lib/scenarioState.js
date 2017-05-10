"use strict";

var _ = require('lodash'),
    Bacon = require('baconjs'),
    F = require('modeling/lib/func.js'),
    Tree = require('modeling/lib/tree.js');

function ScenarioState(strings) {
    var modelParamChangesBus = new Bacon.Bus(),
        replantingChangesBus = new Bacon.Bus(),
        treeChangesBus = new Bacon.Bus(),
        treeUpdatedBus = new Bacon.Bus(),
        locationRemovedBus = new Bacon.Bus(),
        locationChangesBus = new Bacon.Bus(),
        polygonUpdatedBus = new Bacon.Bus(),
        staticState = {},

        modelParamChangesProperty = modelParamChangesBus.scan(
            {},
            function(modelParams, updateAction) {
                return updateAction(modelParams);
            }
        ),

        replantingChangesProperty = replantingChangesBus.scan(
            {},
            function(params, updateAction) {
                return updateAction(params);
            }
        ),

        // Individual trees & Tree distributions in sidebar.
        treeChangesProperty = treeChangesBus.scan(
            [],
            function(trees, updateAction) {
                return updateAction(trees);
            }
        ),

        // Tree locations (map markers).
        locationChangesProperty = locationChangesBus.scan(
            [],
            function(locations, updateAction) {
                return updateAction(locations);
            }
        ),

        // Current polygon GeoJSON.
        polygonChangesProperty = polygonUpdatedBus.toProperty(null),

        stateChangesProperty = Bacon.combineTemplate({
            modelParams: modelParamChangesProperty,
            replanting: replantingChangesProperty,
            trees: treeChangesProperty,
            locations: locationChangesProperty,
            polygonJSON: polygonChangesProperty
        }),

        validationErrorsProperty = stateChangesProperty.map(validate),

        serializedProperty = stateChangesProperty.map(serialize);

    // Sync tree locations with map markers.
    treeChangesProperty.sampledBy(locationChangesProperty, F.argumentsToArray)
        .onValues(function(trees, locations) {
            _.each(trees, function(tree) {
                if (tree.isSingleTree()) {
                    var updatedTree = tree.clone({
                        locations: _.filter(locations, function(loc) {
                            return loc.treeUid() === tree.uid();
                        })
                    });
                    if (!updatedTree.equals(tree)) {
                        updateTree(updatedTree);
                    }
                }
            });
        });

    function addTree(tree) {
        treeChangesBus.push(function(trees) {
            return trees.concat(tree);
        });
    }

    function updateTree(updatedTree) {
        if (updatedTree.quantity() <= 0) {
            removeTreeByUid(updatedTree.uid());
        } else {
            treeChangesBus.push(function(trees) {
                return _.map(trees, function(tree) {
                    return tree.uid() === updatedTree.uid() ?
                        updatedTree : tree;
                });
            });
            treeUpdatedBus.push(updatedTree);
        }
    }

    function removeTreeByUid(uid) {
        treeChangesBus.push(function(trees) {
            return _.filter(trees, function(tree) {
                return tree.uid() != uid;
            });
        });
        removeLocationsByTreeUid(uid);
    }

    function addLocation(loc) {
        locationChangesBus.push(function(locations) {
            return locations.concat(loc);
        });
    }

    function updateLocation(updatedLocation) {
        locationChangesBus.push(function(locations) {
            return _.map(locations, function(loc) {
                return loc.uid() === updatedLocation.uid() ?
                    updatedLocation : loc;
            });
        });
    }

    function removeLocationByUid(uid) {
        locationChangesBus.push(function(locations) {
            return _.filter(locations, function(loc) {
                return loc.uid() != uid;
            });
        });
        locationRemovedBus.push(uid);
    }

    function removeLocationsByTreeUid(treeUid) {
        locationChangesBus.push(function(locations) {
            var result = _.filter(locations, function(loc) {
                return loc.treeUid() != treeUid;
            });
            _.each(_.difference(locations, result), function(loc) {
                locationRemovedBus.push(loc.uid());
            });
            return result;
        });
    }

    function updatePolygon(geoJSON) {
        polygonUpdatedBus.push(geoJSON);
    }

    function updateDefaultMortalityRate(value) {
        modelParamChangesBus.push(function (modelParams) {
            var params = modelParams.mortality.params;
            params.default = value;
            return modelParams;
        });
    }

    // Create new mortality rates row, using values from "Default" row.
    function createMortalityRate(otmCode) {
        modelParamChangesBus.push(function (modelParams) {
            var params = modelParams.mortality.params,
                speciesAndDiameters = params.speciesAndDiameters || [],
                defaultRow = _.find(speciesAndDiameters, {otmCode: 'default'});

            if (defaultRow) {
                speciesAndDiameters.push({
                    otmCode: otmCode,
                    mortalityRates: defaultRow.mortalityRates
                });
            }

            params.speciesAndDiameters = speciesAndDiameters;
            return modelParams;
        });
    }

    // Create the "Default" mortality rates row, if it doesn't exist.
    function createDefaultMortalityRate() {
        modelParamChangesBus.push(function (modelParams) {
            var params = modelParams.mortality.params,
                speciesAndDiameters = params.speciesAndDiameters || [],
                defaultRow = _.find(speciesAndDiameters, {otmCode: 'default'}),
                mortalityRates = _.times(params.diameterBreaksCount, _.constant(params.default));

            if (defaultRow) {
                // Reset mortality rates in case of data corruption.
                if (defaultRow.mortalityRates.length !== mortalityRates.length) {
                    defaultRow.mortalityRates = mortalityRates;
                }
            } else {
                speciesAndDiameters.push({
                    otmCode: 'default',
                    mortalityRates: mortalityRates
                });
            }

            params.speciesAndDiameters = speciesAndDiameters;
            return modelParams;
        });
    }

    function updateMortalityRates(speciesAndDiameters) {
        modelParamChangesBus.push(function (modelParams) {
            var params = modelParams.mortality.params;
            params.speciesAndDiameters = speciesAndDiameters;
            return modelParams;
        });
    }

    function updateMortalityMode(value) {
        modelParamChangesBus.push(function (modelParams) {
            var params = modelParams.mortality.params;
            params.mode = value;
            return modelParams;
        });
    }

    function updateReplanting(enable, nYears) {
        replantingChangesBus.push(function (params) {
            return { enable: enable, nYears: nYears };
        });
    }

    // Return array of validation errors.
    function validate(state) {
        var errors = [],
            distributions = _.filter(state.trees, function(tree) {
                return tree.isDistribution();
            });

        if (state.trees.length === 0) {
            errors.push({
                type: 'misc',
                level: 'warning',
                message: strings.NEED_AT_LEAST_1_TREE
            });
        }

        _.each(state.trees, function(tree) {
            if (isNaN(tree.diameter())) {
                errors.push({
                    type: 'tree',
                    uid: tree.uid(),
                    field: 'diameter',
                    message: strings.INVALID_DIAMETER
                });
            }
            if (isNaN(tree.quantity())) {
                errors.push({
                    type: 'tree',
                    uid: tree.uid(),
                    field: 'quantity',
                    message: strings.INVALID_QUANTITY
                });
            }
        });

        return errors;
    }

    function serializeForSimulation(state) {
        var replanting = state.replanting || '',
            trees = _.invokeMap(
                _.filter(state.trees, function(tree) {
                    return tree.isSingleTree();
                }),
                'serialize'
            ),
            distributions = _.invokeMap(
                _.filter(state.trees, function(tree) {
                    return tree.isDistribution();
                }),
                'serialize'
            ),
            polygonJSON = state.polygonJSON || '';

        return {
            trees: trees,
            distributions: distributions,
            replanting: replanting,
            polygon: polygonJSON
        };
    }

    function serialize(state) {
        return {
            id: staticState.id,
            name: staticState.name,
            scenario_params: serializeForSimulation(state),
            model_params: state.modelParams
        };
    }

    function load(state) {
        var params = state.scenario_params,
            trees = _.map(
                [].concat(params.trees).concat(params.distributions),
                Tree.deserialize
            ),
            locations = _.filter(
                _.flatten(_.invokeMap(trees, 'locations'), true)
            );

        initStaticState(state);
        modelParamChangesBus.push(F.getter(state.model_params));
        replantingChangesBus.push(F.getter(params.replanting));
        treeChangesBus.push(F.getter(trees));
        locationChangesBus.push(F.getter(locations));
        updatePolygon(params.polygon);
    }

    function reset(initialScenario) {
        if (initialScenario) {
            initialScenario = _.clone(initialScenario);
        } else {
            initialScenario = {};
        }
        initStaticState(initialScenario);
        modelParamChangesBus.push(F.getter(initialScenario.model_params));
        replantingChangesBus.push(F.getter(initialScenario.replanting));
        treeChangesBus.push(F.getter([]));
        locationChangesBus.push(F.getter([]));
        updatePolygon(null);
    }

    function initStaticState(scenario) {
        staticState = {
            id: scenario.id,
            name: scenario.name
        };
    }

    return {
        modelParamChangesProperty: modelParamChangesProperty,
        replantingChangesProperty: replantingChangesProperty,
        treeChangesProperty: treeChangesProperty,
        locationChangesProperty: locationChangesProperty,
        polygonChangesProperty: polygonChangesProperty,

        validationErrorsProperty: validationErrorsProperty,
        serializedProperty: serializedProperty,

        treeUpdatedStream: treeUpdatedBus.map(_.identity),
        locationRemovedStream: locationRemovedBus.map(_.identity),

        addTree: addTree,
        updateTree: updateTree,
        removeTreeByUid: removeTreeByUid,
        addLocation: addLocation,
        updateLocation: updateLocation,
        removeLocationByUid: removeLocationByUid,
        removeLocationsByTreeUid:removeLocationsByTreeUid,
        updatePolygon: updatePolygon,
        createMortalityRate: createMortalityRate,
        createDefaultMortalityRate: createDefaultMortalityRate,
        updateMortalityRates: updateMortalityRates,
        updateDefaultMortalityRate: updateDefaultMortalityRate,
        updateMortalityMode: updateMortalityMode,
        updateReplanting: updateReplanting,
        load: load,
        reset: reset
    };
}

module.exports = ScenarioState;
