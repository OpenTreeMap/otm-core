"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    R = require('ramda'),
    toastr = require('toastr'),
    Bacon = require('baconjs'),
    popover = require('treemap/popover'),
    otmTypeahead = require('treemap/otmTypeahead'),
    BU = require('treemap/baconUtils');

var dom = {
    pane: '.tab-pane',
    backLink: 'a[data-action="back"]',
    commitLink: 'a[data-action="commit"]',
    pagingButtons: '.pagination li a',
    rowInMergeRequiredTable: '#import-panel-merge_required .js-import-row',
    mergeControls: '.js-merge-controls',
    hideMergeControlsButton: '.js-hide',
    mergeButton: '.js-merge',
    resolver: {
        popupContainer: '.popover-content',
        saveButton: '.resolver-popover-accept',
        events: {shown: 'shown.bs.popover'},
        species: {input: '.species-resolver-typeahead',
                  hidden: '.species-resolver-typeahead-hidden',
                  typeaheadRowTemplate: '#species-element-template'}
    }
};

function initTypeaheads() {
    // find all species popovers and initialize a typeahead in each one
    // we can't use the event target because it will be the popupTrigger,
    // not the popupContainer.
    _.each($(dom.resolver.popupContainer), function (container) {
        var $c = $(container),
            $input = $c.find(dom.resolver.species.input),
            $hidden = $c.find(dom.resolver.species.hidden);

        // make sure this is a species popover
        if (R.every(R.not(_.isEmpty), [$input, $hidden])) {
            otmTypeahead.create({
                name: "species-resolver",
                template: dom.resolver.species.typeaheadRowTemplate,
                url: $input.attr('data-typeahead-url'),
                input: $input,
                hidden: $hidden,
                reverse: "id",
                forceMatch: true
            });
        }
    });
}

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

    var popoverSaveStream = popover.init($container)
            .map('.currentTarget')
            .map($)
            .filter('.is', dom.resolver.saveButton);

    var isSpeciesPopover = function ($el) { return $el.is('[data-field-name="species"]'); };

    popoverSaveStream.filter(isSpeciesPopover).onValue(updateSpeciesRow, $container);
    popoverSaveStream.filter(R.not(isSpeciesPopover)).onValue(updateRow, $container);

    containerLoadedStream.merge(viewStatusStream).onValue(popover.activateAll);
    $container.on(dom.resolver.events.shown, initTypeaheads);

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
    var rowData = getRowData($container, $el);
    $container.load(rowData.url, rowData.data, popover.activateAll);
}

function updateSpeciesRow($container, $el) {
    var rowData = getRowData($container, $el);
    if (R.every(R.not(_.isEmpty), [rowData.fieldName, rowData.updatedValue])) {
        $container.load(rowData.url, rowData.data, popover.activateAll);
    } else {
        toastr.error("Cannot save empty species");
    }
}

function getRowData($container, $el) {
    var fieldName = $el.attr('data-field-name'),
        updatedValue = $el.parent().find(".popover-correction").val();

    return {
        fieldName: fieldName,
        updatedValue: updatedValue,
        url: $el.attr('data-url'),
        data: _.object([fieldName], [updatedValue])
    };
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
