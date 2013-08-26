"use strict";

// The main "map" page has several modes -- browse trees, add a tree, and edit
// tree details. Each mode has a div in the sidebar to show its UI and a JS
// module to handle UI events. This module initializes the mode modules and
// orchestrates switching between modes.

// Note that different modes will interpret map clicks differently. We pass
// the map's "clickedLatLonStream" to each mode, but filter it so the events
// will be ignored unless the mode is active.

var $ = require('jquery'),
    browseTreesMode     = require('./browseTreesMode'),
    addTreeMode         = require('./addTreeMode'),
    editTreeDetailsMode = require('./editTreeDetailsMode'),
    currentMode;

var $sidebarBrowseTrees     = $('#sidebar-browse-trees'),
    $sidebarAddTree         = $('#sidebar-add-tree'),
    $sidebarEditTreeDetails = $('#sidebar-edit-tree-details');

function activateMode(mode, $sidebar) {
    $sidebar.siblings().hide();
    $sidebar.show();
    if (mode.activate) { mode.activate(); }
    currentMode = mode;
}

function activateBrowseTreesMode()     { activateMode(browseTreesMode,     $sidebarBrowseTrees); }
function activateAddTreeMode()         { activateMode(addTreeMode,         $sidebarAddTree); }
function activateEditTreeDetailsMode() { activateMode(editTreeDetailsMode, $sidebarEditTreeDetails); }

function inBrowseTreesMode()     { return currentMode === browseTreesMode; }
function inAddTreeMode()         { return currentMode === addTreeMode; }
function inEditTreeDetailsMode() { return currentMode === editTreeDetailsMode; }

function init(config, map, clickedLatLonStream) {
    browseTreesMode.init({
        config: config,
        map: map,
        myClickedLatLonStream : clickedLatLonStream.filter(inBrowseTreesMode),
        inMyMode : inBrowseTreesMode,
        $sidebar : $sidebarBrowseTrees
    });

    addTreeMode.init({
        config: config,
        map: map,
        myClickedLatLonStream : clickedLatLonStream.filter(inAddTreeMode),
        $sidebar : $sidebarAddTree,
        onClose : activateBrowseTreesMode
    });

    editTreeDetailsMode.init({
        config: config,
        map: map,
        myClickedLatLonStream : clickedLatLonStream.filter(inEditTreeDetailsMode),
        $sidebar : $sidebarEditTreeDetails,
        onClose : activateBrowseTreesMode
    });
}

module.exports = {
    init: init,
    activateBrowseTreesMode: activateBrowseTreesMode,
    activateAddTreeMode: activateAddTreeMode,
    activateEditTreeDetailsMode: activateEditTreeDetailsMode
};
