"use strict";

var $ = require('jquery'),
    L = require('leaflet'),
    boundarySelect = require('treemap/lib/boundarySelect.js'),
    locationSearchUI = require('treemap/mapPage/locationSearchUI.js');

var map,
    modes,
    originalTooltip,
    customTooltip,
    polygonFeatureGroup,
    editor,
    editsSaved;

var dom = {
    editArea: '.edit-area',
    saveArea: '.save-area',
    cancelEdit: '.cancel-edit',
    searchTriggers: '#perform-search, #species-typeahead'
};

function init(options) {
    map = options.map;
    modes = options.modes;
    originalTooltip = L.drawLocal.edit.handlers.edit.tooltip;
    customTooltip = formatTooltip(options.tooltipStrings);
    polygonFeatureGroup = new L.FeatureGroup();
    editor = new L.EditToolbar.Edit(map, { featureGroup: polygonFeatureGroup });

    $(dom.editArea).on('click', modes.activateEditAreaMode);
    $(dom.saveArea).on('click', saveArea);
    $(dom.cancelEdit).on('click', cancelEditing);
}

function activate() {
    setTooltips(customTooltip);
    locationSearchUI.showEditAreaControls();
    enableSearch(false);

    polygonFeatureGroup.addLayer(boundarySelect.getCurrentLayer());
    editor.enable();

    $(document).on('keydown', onKeyDown);
    editsSaved = false;
}

function onKeyDown(e) {
    if (e.keyCode === 13) {  // Enter key
        saveArea();
    } else if (e.keyCode === 27) {  // Escape key
        cancelEditing();
    }
}

function saveArea() {
    editor.save();
    editsSaved = true;
    locationSearchUI.completePolygon(boundarySelect.getCurrentLayer());
    modes.activateBrowseTreesMode(true);
}

function cancelEditing() {
    modes.activateBrowseTreesMode();
}

function deactivate() {
    setTooltips(originalTooltip);
    locationSearchUI.showCustomAreaControls();
    enableSearch(true);
    if (!editsSaved) {
        editor.revertLayers();
    }
    polygonFeatureGroup.clearLayers();
    editor.disable();
    $(document).off('keydown', onKeyDown);
}

function enableSearch(shouldEnable) {
    $(dom.searchTriggers).prop("disabled", !shouldEnable);
}

function formatTooltip(strings) {
    var kicker = strings.pop(),
        message = strings.join('<br/>');
    return {
        text: format(message, kicker)
    };

    function format(message, kicker) {
        if (kicker) {
            message += '<br/><i>' + kicker + '</i>';
        }
        return message;
    }
}

function setTooltips(tooltips) {
    L.drawLocal.edit.handlers.edit.tooltip = tooltips;
}

module.exports = {
    name: 'editArea',
    init: init,
    activate: activate,
    deactivate: deactivate
};
