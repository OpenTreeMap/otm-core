"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    U = require('treemap/utility'),
    addMapFeature = require('treemap/addMapFeature'),
    otmTypeahead = require('treemap/otmTypeahead'),
    diameterCalculator = require('treemap/diameterCalculator');

var manager,
    STEP_LOCATE = 0,
    STEP_DETAILS = 1,
    STEP_FINAL = 2;

function init(options) {
    var $sidebar = $(options.sidebar),
        $addressInput = U.$find('.form-search input', $sidebar),
        $speciesTypeahead = U.$find('#add-tree-species-typeahead', $sidebar),
        $speciesInput = U.$find('[data-typeahead-input="tree.species"]', $sidebar),
        $summaryHead = U.$find('.summaryHead', $sidebar),
        $summarySubhead = U.$find('.summarySubhead', $sidebar);

    manager = addMapFeature.init(options);

    otmTypeahead.bulkCreate(options.typeaheads);

    diameterCalculator({ formSelector: options.formSelector,
                         cancelStream: manager.deactivateStream,
                         saveOkStream: manager.addFeatureStream });

    manager.stepChangeCompleteStream.onValue(function (stepNumber) {
        if (stepNumber === STEP_LOCATE) {
            focusOnAddressInput();
        } else if (stepNumber === STEP_DETAILS) {
            if ($speciesInput.val().length === 0) {
                $speciesInput.focus();
            }
        }
    });

    manager.stepChangeStartStream.onValue(function (stepNumber) {
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

    function focusOnAddressInput() {
        if ($addressInput.val().length === 0) {
            $addressInput.focus();
        }
    }

    _.defer(function () {
        focusOnAddressInput();
    });
}

function activate() {
    if (manager) {
        manager.activate();
    }
}

function deactivate() {
    if (manager) {
        manager.deactivate();
    }
}

module.exports = {
    name: 'addTree',
    init: init,
    activate: activate,
    deactivate: deactivate,
    lockOnActivate: true
};
