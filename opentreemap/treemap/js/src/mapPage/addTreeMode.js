"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    U = require('treemap/lib/utility.js'),
    addMapFeature = require('treemap/mapPage/addMapFeature.js'),
    otmTypeahead = require('treemap/lib/otmTypeahead.js'),
    plotMarker = require('treemap/lib/plotMarker.js'),
    diameterCalculator = require('treemap/lib/diameterCalculator.js');

var activateMode = _.identity,
    deactivateMode = _.identity,
    STEP_LOCATE = 0,
    STEP_DETAILS = 1,
    STEP_FINAL = 2;

function init(options) {
    var $sidebar = $(options.sidebar),
        $speciesTypeahead = U.$find('#add-tree-species-typeahead', $sidebar),
        $summaryHead = U.$find('.summaryHead', $sidebar),
        $summarySubhead = U.$find('.summarySubhead', $sidebar),
        typeahead = otmTypeahead.create(options.typeahead),
        clearEditControls = function() {
            typeahead.clear();
        },
        manager = addMapFeature.init(_.extend({clearEditControls: clearEditControls}, options));

    activateMode = function() {
        manager.activate();
        // Let user start creating a feature (by clicking the map)
        plotMarker.useTreeIcon(true);
        plotMarker.enablePlacing();
        $('body').addClass('add-feature');
    };

    deactivateMode = function() {
        typeahead.clear();
        manager.deactivate();
    };

    diameterCalculator({ formSelector: options.formSelector,
                         cancelStream: manager.deactivateStream,
                         saveOkStream: manager.addFeatureStream });

    manager.stepControls.stepChangeStartStream.onValue(function (stepNumber) {
        if (stepNumber === STEP_FINAL) {
            var species = $speciesTypeahead.data('datum'),
                common_name = species ? species.common_name :
                              aTreeFieldIsSet() ? "Missing species" : "Empty planting site",
                scientific_name = species ? species.scientific_name : '';
            $summaryHead.text(common_name);
            $summarySubhead.text(scientific_name);
        }
    });

    function aTreeFieldIsSet() {
        var data = manager.getFormData();
        return _.some(data, function (value, key) {
            return key && key.indexOf('tree') === 0 && value;
        });
    }

    // In case we're adding another tree, make user move the marker
    manager.addFeatureStream.onValue(manager.requireMarkerDrag);
}

function activate() {
    activateMode();
}

function deactivate() {
    deactivateMode();
}

module.exports = {
    name: 'addTree',
    hideSearch: true,
    init: init,
    activate: activate,
    deactivate: deactivate,
    lockOnActivate: true
};
