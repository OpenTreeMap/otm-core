"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    template = require('modeling/lib/template.js');

var dom = {
        defaultMortalityInput: '#tree-mortality-container input[data-category="default"]',
        editMortalityRatesButton: '#edit-mortality-rates',
        mortalityModeRadio: '#tree-mortality-container [name="mortality-mode"]',
        mortalityRateModal: '#mortality-rate-modal',
        mortalityRateSave: '#mortality-rate-modal button.save',
        mortalityRateTable: '#mortality-rate-table',
        mortalityRateInput: '#mortality-rate-table input[type="number"]',
        mortalityRateDropdownButton: '#mortality-rate-dropdown > button',
        mortalityRateDropdownMenu: '#mortality-rate-dropdown > .dropdown-menu',
        createMortalityRate: '[data-action="create"]',
        removeMortalityRate: '[data-action="remove"]',
        replanting: {
            enable: '#replanting-growth-container input[type="checkbox"]',
            nYears: '#replanting-growth-container input[type="number"]',
            all: '#replanting-growth-container input'
        }
    },

    templates = {
        mortalityRateRow: '#mortality-rate-row-tmpl',
        mortalityRateDropdownItem: '#mortality-rate-dropdown-item-tmpl'
    };

var _state = null,
    _species = null,
    _speciesCodes = null,
    _strings = window.modelingOptions.strings;

module.exports = {
    init: init
};

function init(scenarioState, species) {
    _state = scenarioState;
    _species = species;

    _speciesCodes = _.map(_species, function(species) {
        return species.otm_code;
    });

    _state.modelParamChangesProperty.onValue(updateDefaultMortalityRate);
    _state.modelParamChangesProperty.onValue(updateMortalityRateModal);
    _state.modelParamChangesProperty.onValue(updateMortalityMode);
    _state.replantingChangesProperty.onValue(updateReplanting);

    $(dom.defaultMortalityInput)
        .asEventStream('blur')
        .onValue(onDefaultMortalityRateChanged);
    $(dom.mortalityModeRadio)
        .asEventStream('click')
        .onValue(onMortalityModeChanged);
    $(dom.mortalityRateTable)
        .asEventStream('click', dom.removeMortalityRate)
        .onValue(removeMortalityRate);
    $(dom.mortalityRateSave)
        .asEventStream('click')
        .onValue(saveMortalityRates);
    $(dom.replanting.all)
        .asEventStream('blur')
        .onValue(onReplantingChanged);

    _state.modelParamChangesProperty.sampledBy(
        $(dom.editMortalityRatesButton)
            .asEventStream('click')
    ).onValue(showMortalityRateModal);

    // Sample modelParams property while also preserving the click event.
    _state.modelParamChangesProperty.sampledBy(
        $(dom.mortalityRateModal)
            .asEventStream('click', dom.createMortalityRate),
        function(modelParams, clickEvent) {
            return {
                modelParams: modelParams,
                clickEvent: clickEvent
            };
        }
    ).onValue(createMortalityRate);
}

function updateMortalityMode(modelParams) {
    if (modelParams && modelParams.mortality) {
        var params = modelParams.mortality.params;
        if (params.mode === 'default') {
            $(dom.mortalityModeRadio + '[value=default]').prop('checked', true);
            $(dom.defaultMortalityInput).prop('disabled', false);
            $(dom.editMortalityRatesButton).prop('disabled', true);
        } else {
            $(dom.mortalityModeRadio + '[value=speciesAndDiameters]').prop('checked', true);
            $(dom.defaultMortalityInput).prop('disabled', true);
            $(dom.editMortalityRatesButton).prop('disabled', false);
        }
    }
}

function onMortalityModeChanged(e) {
    var $item = $(e.currentTarget);
    _state.updateMortalityMode($item.val());
}

function updateDefaultMortalityRate(modelParams) {
    if (modelParams && modelParams.mortality) {
        var params = modelParams.mortality.params;
        $(dom.defaultMortalityInput).val(params.default);
    }
}

function onDefaultMortalityRateChanged(e) {
    var $item = $(e.currentTarget),
        value = parseFloat($item.val());
    _state.updateDefaultMortalityRate(value);
}

function showMortalityRateModal(modelParams) {
    if (modelParams && modelParams.mortality) {
        var params = modelParams.mortality.params,
            selectedCodes = _.map(params.speciesAndDiameters, 'otmCode');

        _state.createDefaultMortalityRate();

        updateAddSpeciesDropdown(selectedCodes);
        $(dom.mortalityRateModal).modal('show');
    }
}

function updateMortalityRateModal(modelParams) {
    if (modelParams && modelParams.mortality) {
        var params = modelParams.mortality.params,
            rows = _.map(params.speciesAndDiameters, function(item) {
                return createMortalityRateRow(params, item);
            }),
            $tbody = $('<tbody>');
        $tbody.append(rows);
        $(dom.mortalityRateTable).find('tbody').replaceWith($tbody);
    }
}

function createMortalityRate(args) {
    var modelParams = args.modelParams,
        e = args.clickEvent;

    if (modelParams && modelParams.mortality) {
        var params = modelParams.mortality.params,
            $el = $(e.currentTarget),
            otmCode = $el.data('code'),
            item = {
                otmCode: otmCode,
                mortalityRates: []
            },
            $row = $(createMortalityRateRow(params, item));

        $(dom.mortalityRateTable).find('tbody').append($row);
        $row.find('input').trigger('first').trigger('select');
        updateAddSpeciesDropdown(getSelectedCodesFromUI());
    }
}

function removeMortalityRate(e) {
    var $el = $(e.currentTarget),
        otmCode = $el.data('code');
    $el.parents('tr').remove();
    updateAddSpeciesDropdown(getSelectedCodesFromUI());
}

function getSelectedCodesFromUI() {
    var selectedCodes = $(dom.mortalityRateInput).map(function() {
        return $(this).data('code');
    });
    return _.uniq(selectedCodes);
}

function createMortalityRateRow(params, item) {
    return template.render(templates.mortalityRateRow, {
        otmCode: item.otmCode,
        commonName: findCommonName(item.otmCode),
        mortalityRates: item.mortalityRates,
        diameterBreaksCount: params.diameterBreaksCount
    });
}

function saveMortalityRates() {
    var speciesAndDiameters = generateSpeciesAndDiameters();
    _state.updateMortalityRates(speciesAndDiameters);
}

// Generate mortality rates per species data structure
// based on the mortality rates table UI.
function generateSpeciesAndDiameters() {
    var result = [];
    $(dom.mortalityRateInput).each(function(i, el) {
        var $el = $(this),
            otmCode = $el.data('code'),
            diameterIndex = $el.data('index'),
            value = parseFloat($el.val()),
            item = _.find(result, {otmCode: otmCode});

        if (!item) {
            item = {
                otmCode: otmCode,
                mortalityRates: []
            };
            result.push(item);
        }

        item.mortalityRates[diameterIndex] = value;
    });
    return result;
}

function updateAddSpeciesDropdown(selectedSpeciesCodes) {
    // Difference between selected species and available species.
    var choices = _.difference(_speciesCodes, selectedSpeciesCodes),

        $dropdownMenu = $(dom.mortalityRateDropdownMenu),
        $dropdownButton = $(dom.mortalityRateDropdownButton),
        listItems = _.map(choices, createSpeciesListItem);

    $dropdownMenu.empty().append(listItems);
    $dropdownButton.toggleClass('disabled', listItems.length === 0);
}

function createSpeciesListItem(otmCode) {
    return template.render(templates.mortalityRateDropdownItem, {
        otmCode: otmCode,
        commonName: findCommonName(otmCode)
    });
}

function updateReplanting(params) {
    if (params) {
        $(dom.replanting.nYears).val(params.nYears);
        $(dom.replanting.enable).prop('checked', params.enable);
    }
}

function onReplantingChanged() {
    var enable = $(dom.replanting.enable).prop('checked'),
        nYears = parseInt($(dom.replanting.nYears).val(), 10);
    _state.updateReplanting(enable, nYears);
}

function findCommonName(otmCode) {
    if (otmCode === 'default') {
        return _strings.DEFAULT;
    }
    var species = _.find(_species, {otm_code: otmCode});
    return species && species.common_name || '';
}
