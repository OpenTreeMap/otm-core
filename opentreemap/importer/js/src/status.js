"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils');

var dom = {
    pane: '.tab-pane',
    backLink: 'a[data-action="back"]',
    pagingButtons: '.pagination li a'
};

function init($container) {
    BU.reloadContainerOnClick($container, dom.backLink);

    $container.asEventStream('click', dom.pagingButtons)
        .onValue(reloadPane);
}

function reloadPane(e) {
    var button = e.target,
        $pane = $(button).closest(dom.pane);
    e.preventDefault();
    $pane.load(button.href);
}

module.exports = {init: init};
