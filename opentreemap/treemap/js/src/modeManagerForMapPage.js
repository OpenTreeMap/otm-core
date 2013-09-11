"use strict";

// The main "map" page has several modes -- browse trees, add a tree, and edit
// tree details. Each mode has a div in the sidebar to show its UI and a JS
// module to handle UI events. This module initializes the mode modules and
// orchestrates switching between modes.

var U = require('./utility'),
    browseTreesMode     = require('./browseTreesMode'),
    addTreeMode         = require('./addTreeMode'),
    editTreeDetailsMode = require('./editTreeDetailsMode'),
    inlineEditForm      = require('./inlineEditForm'),
    plotMarker          = require('./plotMarker'),
    currentMode;

var $sidebarBrowseTrees         = U.$find('#sidebar-browse-trees'),
    $treeDetailAccordionSection = U.$find('#tree-detail'),
    $sidebarAddTree             = U.$find('#sidebar-add-tree'),
    $fullDetailsButton          = U.$find('#full-details-button');

function activateMode(mode, $sidebar) {
    if (mode !== currentMode) {
        if (currentMode && currentMode.deactivate) {
            currentMode.deactivate();
        }
        $sidebar.siblings().hide();
        $sidebar.show();
        if (mode.activate) {
            mode.activate();
        }
        currentMode = mode;
    }
}

function activateBrowseTreesMode()     { activateMode(browseTreesMode,     $sidebarBrowseTrees); }
function activateAddTreeMode()         { activateMode(addTreeMode,         $sidebarAddTree); }
function activateEditTreeDetailsMode() { activateMode(editTreeDetailsMode, $sidebarBrowseTrees); }

function inBrowseTreesMode() { return currentMode === browseTreesMode; }
function inAddTreeMode()     { return currentMode === addTreeMode; }

function init(config, mapManager) {
    // browseTreesMode and editTreeDetailsMode share an inlineEditForm,
    // so initialize it here.
    inlineEditForm.init({
        updateUrl: '', // set in browseTreesMode.js on map click
        form: '#details-form',
        edit: '#edit-details-button',
        save: '#save-details-button',
        cancel: '#cancel-edit-details-button',
        displayFields: '#sidebar-browse-trees [data-class="display"]',
        editFields: '#sidebar-browse-trees [data-class="edit"]',
        validationFields: '#sidebar-browse-trees [data-class="error"]',
        onSaveBefore: editTreeDetailsMode.onSaveBefore
    });
    inlineEditForm.inEditModeProperty.onValue(function (inEditMode) {
        // Form is changing to edit mode or display mode
        if (inEditMode) {
            activateEditTreeDetailsMode();
        } else {
            activateBrowseTreesMode();
        }
    });

    plotMarker.init(mapManager.map);

    browseTreesMode.init({
        config: config,
        map: mapManager.map,
        inMyMode: inBrowseTreesMode,
        $treeDetailAccordionSection: $treeDetailAccordionSection,
        $fullDetailsButton: $fullDetailsButton,
        inlineEditForm: inlineEditForm,
        plotMarker: plotMarker
    });

    addTreeMode.init({
        config: config,
        mapManager: mapManager,
        plotMarker: plotMarker,
        inMyMode: inAddTreeMode,
        $sidebar: $sidebarAddTree,
        onClose: activateBrowseTreesMode,
        typeaheads: [getSpeciesTypeaheadOptions(config, "add-tree-species")]
    });

    editTreeDetailsMode.init({
        mapManager: mapManager,
        inlineEditForm: inlineEditForm,
        plotMarker: plotMarker,
        typeaheads: [getSpeciesTypeaheadOptions(config, "edit-tree-species")]
    });
}

function getSpeciesTypeaheadOptions(config, idPrefix) {
    return {
        name: "species",
        url: "/" + config.instance.url + "species",
        input: "#" + idPrefix + "-typeahead",
        template: "#species-element-template",
        hidden: "#" + idPrefix + "-hidden",
        reverse: "id"
    }
}

module.exports = {
    init: init,
    activateBrowseTreesMode: activateBrowseTreesMode,
    activateAddTreeMode: activateAddTreeMode
};
