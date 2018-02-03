"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    toastr = require('toastr'),
    dragula = require('dragula');

var dom = {
        mainContainer: '#field-groups',
        fieldGroupContainer: '[data-item="group-container"]',

        displayItems: '[data-class="display"]',
        editableItems: '[data-class="edit"]',

        fieldHandle: '[data-action="field-handle"]',
        groupHandle: '[data-action="group-handle"]',
        up: '[data-action="up"]',
        down: '[data-action="down"]',
        fieldToggle: '[data-action="field-toggle"]',

        sortableRow: '[data-sortable]',

        groups: '[data-item="field-group"]',
        listContainer: '[data-item="field-lists"]',
        enabledLists: '[data-item="enabled-fields"]',
        disabledLists: '[data-item="disabled-fields"]',
    };

exports.enabledFor = function($group) {
    return $group.find(dom.enabledLists);
};

exports.groupContainer = function($group) {
    return $group.closest(dom.fieldGroupContainer);
};

exports.handle = function(options) {
    var url = options.url,
        $container = $(options.container),
        $editButton = $(options.editButton),
        $saveButton = $(options.saveButton),
        $cancelButton = $(options.cancelButton),

        $mainContainer = $(dom.mainContainer);

    setupDrag();

    $editButton.on('click', function(e) {
        showEdit(true);
    });

    function showEdit(isEdit) {
        $(dom.groups).toggleClass('edit', isEdit);
        $container.find(dom.displayItems)
            .css('display', '')
            .toggleClass('hidden', isEdit);
        $container.find(dom.editableItems)
            .css('display', '')
            .toggleClass('hidden', !isEdit);
    }

    function setupDrag() {
        $(dom.fieldGroupContainer).each(function(i, elem) {
            dragula([elem], {
                moves: function(el, container, handle) {
                    return $(handle).is(dom.groupHandle);
                }
            });
        });

        $(dom.enabledLists).each(function(i, elem) {
            dragula([elem], {
                moves: function(el, container, handle) {
                    return $(handle).is(dom.fieldHandle);
                }
            });
        });
    }

    $saveButton.on('click', function() {
        $saveButton.prop('disabled', true);
        var data = options.getFieldData($container.find(dom.groups));
        $.ajax({
            url: url,
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function() {
                showEdit(false);
            },
            complete: function() {
                $saveButton.prop('disabled', false);
            },
            error: function(resp) {
                if (resp.responseJSON && resp.responseJSON.fieldErrors &&
                    resp.responseJSON.fieldErrors.mobile_api_fields) {
                    var vals = _.values(resp.responseJSON.fieldErrors.mobile_api_fields);

                    toastr.error(
                        '<ul><li>' + vals.join('</li><li>') + '</li></ul>');
                } else {
                    options.errorCallback(resp);
                }
            }
        });
    });

    $cancelButton.on('click', function() {
        $cancelButton.prop('disabled', true);
        $mainContainer.load(url + ' ' + dom.mainContainer, function() {
            showEdit(false);
            $cancelButton.prop('disabled', false);
            // Because we reloaded the DOM, we need to setup drag events again
            setupDrag();
        });
    });

    $container.on('click', dom.up, function(e) {
        var $row = $(e.target).closest(dom.sortableRow);
        $row.insertBefore($row.prev());
    });
    $container.on('click', dom.down, function(e) {
        var $row = $(e.target).closest(dom.sortableRow);
        $row.insertAfter($row.next());
    });

    $container.on('change', dom.fieldToggle, function(e) {
        var $link = $(e.target).closest(dom.fieldToggle),
            $row = $link.closest(dom.sortableRow),
            $newList;

        // If in enabled list move to disabled list, otherwise reverse
        if ($row.parents(dom.enabledLists).length > 0) {
            $newList = $row.closest(dom.listContainer).find(dom.disabledLists);
            $row.detach().prependTo($newList);
        } else {
            $newList = $row.closest(dom.listContainer).find(dom.enabledLists);
            $row.detach().appendTo($newList);
        }
    });
};
