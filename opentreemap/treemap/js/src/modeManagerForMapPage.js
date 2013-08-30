"use strict";

// The main "map" page has several modes -- browse trees, add a tree, and edit
// tree details. Each mode has a div in the sidebar to show its UI and a JS
// module to handle UI events. This module initializes the mode modules and
// orchestrates switching between modes.

var U = require('./utility'),
    browseTreesMode     = require('./browseTreesMode'),
    addTreeMode         = require('./addTreeMode'),
    editTreeDetailsMode = require('./editTreeDetailsMode'),
    currentMode;

var $sidebarBrowseTrees         = U.$find('#sidebar-browse-trees'),
    $treeDetailAccordionSection = U.$find('#tree-detail'),
    $sidebarAddTree             = U.$find('#sidebar-add-tree'),
    $sidebarEditTreeDetails     = U.$find('#sidebar-edit-tree-details');

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
function activateEditTreeDetailsMode() { activateMode(editTreeDetailsMode, $sidebarEditTreeDetails); }

function inBrowseTreesMode()     { return currentMode === browseTreesMode; }
function inAddTreeMode()         { return currentMode === addTreeMode; }
function inEditTreeDetailsMode() { return currentMode === editTreeDetailsMode; }

function init(config, map, onPlotAddOrUpdate) {
    browseTreesMode.init({
        config: config,
        map: map,
        inMyMode: inBrowseTreesMode,
        $sidebar: $sidebarBrowseTrees,
        $treeDetailAccordionSection: $treeDetailAccordionSection
    });

    addTreeMode.init({
        config: config,
        map: map,
        $sidebar: $sidebarAddTree,
        onAddTree: onPlotAddOrUpdate,
        onClose: activateBrowseTreesMode
    });

    editTreeDetailsMode.init({
        config: config,
        map: map,
        $sidebar: $sidebarEditTreeDetails,
        onClose: activateBrowseTreesMode
    });
}

module.exports = {
    init: init,
    activateBrowseTreesMode: activateBrowseTreesMode,
    activateAddTreeMode: activateAddTreeMode,
    activateEditTreeDetailsMode: activateEditTreeDetailsMode
};
