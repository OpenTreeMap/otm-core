"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    R = require('ramda'),
    toastr = require('toastr'),
    Bacon = require('baconjs'),
    popover = require('treemap/popover'),
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

function init($container, viewStatusStream) {
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

    popover.init($container)
        .map('.currentTarget')
        .map($)
        .filter('.is', '.resolver-popover-accept')
        .onValue(updateRow, $container);

    containerLoadedStream.merge(viewStatusStream).onValue(popover.activateAll);

    // Return the containerLoadedStream so importLists.js knows to start
    // polling for updates
    return containerLoadedStream;
}

function reloadPane(e) {
    var button = e.currentTarget,
        $pane = $(button).closest(dom.pane);
    e.preventDefault();
    $pane.load(button.href, popover.activateAll);
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

function updateRow($container, $el) {
    var fieldName = $el.attr('data-field-name'),
        updatedValue = $el.parent().find(".popover-correction").val(),
        url = $el.attr('data-url'),
        data = _.object([fieldName], [updatedValue]);
    if (R.every(R.not(_.isEmpty), [fieldName, updatedValue])) {
        $container.load(url, data, popover.activateAll);
    } else {
        toastr.error("Cannot save empty species");
    }
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
