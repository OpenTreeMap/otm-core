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
    currentMode;

var $sidebarBrowseTrees         = U.$find('#sidebar-browse-trees'),
    $treeDetailAccordionSection = U.$find('#tree-detail'),
    $sidebarAddTree             = U.$find('#sidebar-add-tree');

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

function inBrowseTreesMode()     { return currentMode === browseTreesMode; }

function init(config, map, onPlotAddOrUpdate) {
    // browseTreesMode and editTreeDetailsMode share an inlineEditForm,
    // so initialize it here.
    inlineEditForm.init({
          updateUrl: "look it up",         // TODO
          form: '#details-form',
          edit: '#edit-details-button',
          save: '#save-details-button',
          cancel: '#cancel-edit-details-button',
          displayFields: '[data-class="display"]',
          editFields: '[data-class="edit"]',
          validationFields: '[data-class="error"]'
    });
    inlineEditForm.inEditModeProperty.onValue(function (inEditMode) {
        // Form is changing to edit mode or display mode
        if (inEditMode) {
            activateEditTreeDetailsMode();
        } else {
            activateBrowseTreesMode();
        }
    });

    browseTreesMode.init({
        config: config,
        map: map,
        inMyMode: inBrowseTreesMode,
        $treeDetailAccordionSection: $treeDetailAccordionSection,
        inlineEditForm: inlineEditForm
    });

    addTreeMode.init({
        config: config,
        map: map,
        $sidebar: $sidebarAddTree,
        onAddTree: onPlotAddOrUpdate,
        onClose: activateBrowseTreesMode
    });

    editTreeDetailsMode.init({
        map: map,
        inlineEditForm: inlineEditForm
    });
}

module.exports = {
    init: init,
    activateBrowseTreesMode: activateBrowseTreesMode,
    activateAddTreeMode: activateAddTreeMode
};
