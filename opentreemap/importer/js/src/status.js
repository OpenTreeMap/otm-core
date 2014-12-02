"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils');

var dom = {
    pane: '.tab-pane',
    backLink: 'a[data-action="back"]',
    commitLink: 'a[data-action="commit"]',
    pagingButtons: '.pagination li a',
    rowInMergeRequiredTable: '#import-panel-merge_required .js-import-row',
    mergeControls: '.js-merge-controls',
    hideMergeControlsButton: '.js-hide',
    mergeButton: '.js-merge'
};

function init($container) {
    // Define events on the container so we can replace its contents
    var containerLoadedStream = BU.reloadContainerOnClick($container, dom.backLink, dom.commitLink);

    $container.asEventStream('click', dom.pagingButtons)
        .onValue(reloadPane);

    $container.asEventStream('click', dom.rowInMergeRequiredTable)
        .onValue(toggleMergeControls);

    $container.asEventStream('click', dom.hideMergeControlsButton)
        .onValue(hideMergeControls);

    $container.asEventStream('click', dom.mergeButton)
        .flatMap(mergeRow)
        .onValue($container, 'html');

    // Return the containerLoadedStream so importLists.js knows to start
    // polling for updates
    return containerLoadedStream;
}

function reloadPane(e) {
    var button = e.currentTarget,
        $pane = $(button).closest(dom.pane);
    e.preventDefault();
    $pane.load(button.href);
}

function toggleMergeControls(e) {
    $(e.target)
        .closest(dom.rowInMergeRequiredTable)
        .next()
        .toggle('fast');
}

function hideMergeControls(e) {
    $(e.target)
        .closest(dom.mergeControls)
        .hide('fast');
}

function mergeRow(e) {
    e.preventDefault();
    var $button = $(e.target),
        url = $button.data('href'),
        data = getMergeData($button);

    $(dom.mergeButton).prop('disabled', true);

    return Bacon.fromPromise(
        $.post(url, {data: JSON.stringify(data)}));
}

function getMergeData($button) {
    var $mergeControls = $button.closest(dom.mergeControls),
        mergeFieldNames = $button.data('merge-field-names').split(','),
        radioGroupNames = $button.data('radio-group-names').split(','),
        data = {};

    _.each(_.zip(mergeFieldNames, radioGroupNames),
        function(fieldName, radioGroupName) {
            var value = $mergeControls
                .find("input:radio[name='" + radioGroupName + "']:checked")
                .val();
            data[fieldName] = value;
        });
    return data;
}

module.exports = {init: init};
