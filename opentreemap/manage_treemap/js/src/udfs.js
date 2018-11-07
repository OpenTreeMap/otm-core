"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    BU = require('treemap/lib/baconUtils.js'),
    U = require('treemap/lib/utility.js'),
    alerts = require('treemap/lib/alerts.js'),
    inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    modalMultiCancel = require('manage_treemap/lib/modalMultiCancel.js'),
    toastr = require('toastr'),
    errors = require('manage_treemap/lib/errors.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

var dom = {
    udfContainer: '[data-udf]',
    choiceList: '[data-item="choices-list"]',
    choice: '[data-item="choice"]',
    choiceInput: '[data-item="choice"] input',

    // Trash can on the choice item in Edit mode
    choiceDelete: '[data-action="delete"]',

    // Display only choice list
    choices: '.choice-udf-choices',
    existingChoice: '[data-udf-choice]',
    addChoiceContainer: '#udf-create-choices',
    trashCan: '[data-item="deleted-choices"]',
    deletedChoice: '[data-marked="delete"]',
    emptyError: '[data-item="empty"]',
    originalChoice: '[data-original-choice]',
    displayChoice: '[data-choice]',
    showAllLess: '[data-less-more]',
    saveModal: '#save-udf-panel',
    saveConfirm: '[data-action="save"]',

    udfs: '#udf-info',

    saveBtn: '.saveBtn',
    cancelBtn: '.cancelBtn',

    udfCreate: '#udf-create',
    createNewUdf: '#create-new-udf',
    createUdfPopup: '#add-udf-panel',
    udfFieldsContainer: '#udf-create-fields',
    createErrors: '#udf-create-errors',

    deletePopupBtnSelector: '[data-udf-delete-popup]',
    deleteBtnSelector: '[data-udf-delete]',
    udfDeletePopup: '#delete-udf-panel',
};

var $udfType = $('#udf-type'),
    $udfModel = $('#udf-model'),

    choiceTemplate = _.template($('#choice-template').html()),
    displayChoiceTemplate = _.template($('#display-choice-template').html()),
    saveConfirmModelTemplate = _.template($('#confirmer-model-template').html()),
    saveConfirmChangeTemplate = _.template($('#confirmer-change-template').html()),

    url = reverse.udfs(config.instance.url_name);

var saveModal = (function() {
    function hide() {
        $(dom.saveModal).hide();
    }

    function anyRenames(data) {
        return _.some(data.choice_changes, function(chch) {
            return _.some(chch.changes, {action: 'rename'});
        });
    }

    function populate(data) {
        var choiceChanges = _.map(data.choice_changes, function(changeSpec) {
            var $container = $(dom.udfs)
                    .find('[data-udf="' + changeSpec.id + '"]');

            var filledInChanges = _.map(changeSpec.changes, function(changeSpec) {
                var displayOriginal = changeSpec.original_value || 'new choice',
                    displayNew = changeSpec.action === 'delete' ?
                        'deleted' : changeSpec.new_value;

                return saveConfirmChangeTemplate({
                    originalValue: displayOriginal,
                    newValue: displayNew
                });
            });

            return saveConfirmModelTemplate({
                udfName: $container.find('td:first').text(),
                changes: filledInChanges.join('')
            });
        });
        return choiceChanges.join('');
    }

    var ok = $('body')
        .asEventStream('click', dom.saveModal + ' ' + dom.saveConfirm)
        .doAction('.preventDefault')
        .doAction(hide);

    return {
        show: function(data) {
            $(dom.saveModal).find('.modal-body .change-info').html(populate(data));
            $(dom.saveModal).modal('show');
            if (anyRenames(data)) {
                $('.rename-warning').show();
            } else {
                $('.rename-warning').hide();
            }
        },
        okStream: ok,
        cancelStream: modalMultiCancel.init({modalSelector: dom.saveModal,
                                             okStream: ok })
    };
})();

U.modalsFocusOnFirstInputWhenShown();

var lessMoreStream = $('#udfs')
    .asEventStream('click', '[data-less-more]')
    .map('.target')
    .map($)
    .map('.parent');

lessMoreStream.onValue(function($showAll) {
    var $choices = $showAll.closest(dom.choices);
    $choices.toggleClass('less more');
});

$udfType.on('change', function(e) {
    var showChoices = _.includes(['choice', 'multichoice'], $(e.currentTarget).val());
    $(dom.createUdfPopup).children('.modal-dialog').toggleClass('modal-lg', showChoices);
    $(dom.udfFieldsContainer).toggleClass('col-xs-12', !showChoices).toggleClass('col-xs-6', showChoices);
    $(dom.addChoiceContainer).toggleClass('col-xs-0', !showChoices).toggleClass('col-xs-6', showChoices);
});

var newUdfStream = $(dom.createNewUdf)
    .asEventStream('click')
    .doAction(function() {
        $(dom.createNewUdf).prop('disabled', true);
    })
    .map(getNewUdfParams)
    .flatMap(BU.jsonRequest('POST', url));

newUdfStream.onValue(addNewUdf);

newUdfStream
    .errors()
    .mapError(errors.convertErrorObjectIntoHtml)
    .onValue($(dom.createErrors), 'html');

newUdfStream
    .mapError()
    .onValue(function() {
        $(dom.createNewUdf).prop('disabled', false);
    });

var getUdfUrlForId = function(id) {
    return reverse.udfs_change({
        instance_url_name: config.instance.url_name,
        udf_id: id
    });
};

$(dom.udfs)
    .asEventStream('click', dom.deletePopupBtnSelector)
    .map('.target')
    .map($)
    .map('.closest', dom.udfContainer)
    .map('.attr', 'data-udf')
    .map(getUdfUrlForId)
    .onValue(function (url) {
        $(dom.udfDeletePopup).load(url, function () {
            $(this).modal('show');
        });
    });

var deleteResponseStream = $(dom.udfDeletePopup)
    .asEventStream('click', dom.deleteBtnSelector)
    .map('.target')
    .flatMap(function (elem) {
        var id = $(elem).attr('data-udf-delete'),
            url = getUdfUrlForId(id);

        var stream = BU.jsonRequest('DELETE', url)();
        stream.onValue(function() {
            $('[data-udf="' + id + '"]').remove();
        });

        return stream;
    });

deleteResponseStream.onError(function(resp) {
    toastr.error(resp.responseText);
});

$('body').on('keydown paste cut', dom.choiceInput, function(e) {
    if (e.keyCode === 13) {
        // For some reason enter triggers a "click" on the delete button...
        // This prevents it
        e.preventDefault();
        return;
    }
    _.defer(function() {
        var $input = $(e.target),
            $choice = $input.closest(dom.choice),
            $choiceList = $choice.closest(dom.choiceList);

        if ($input.val().length > 0 && $choice.is(':last-child')) {
            addChoice($choiceList);
        }
        validate($choiceList, $choice, $input);
        checkDuplicates($choiceList, $choice, $input);
        enableDisableSaveBtn();
        enableDisableCreateBtn();
    });
});
$('body').on('blur', dom.choiceInput, function(e) {
    _.defer(function() {
        var $input = $(e.target),
            $choice = $input.closest(dom.choice),
            $choiceList = $choice.closest(dom.choiceList);

        if ($input.val().length === 0 &&
                !$choice.is(':last-child') &&
                !$choice.data('udf-choice') &&
                $choiceList.children().length > 1) {
            removeChoice($choice);
        }
    });
});
$('body').on('click', dom.choice + ' ' + dom.choiceDelete, function(e) {
    var $icon = $(e.target),
        $button = $icon.closest('button,a'),
        $choice = $button.closest(dom.choice);

    if (0 === $choice.closest(dom.addChoiceContainer).length) {
        prepareChoiceForRemoval($button, $choice);
    } else {
        removeChoice($choice);
    }
});

function prepareChoiceForRemoval($trashButton, $choice) {
    var $choiceList = $choice.closest(dom.choiceList),
        $udf = $choiceList.closest(dom.udfContainer),
        $trashCan = $udf.find(dom.trashCan);

    if ($choice.is(dom.existingChoice)) {
        removeChoice($choice, true) // true means keep.
            .then(function () {
                $choice.attr('data-marked', 'delete');
                $choice.appendTo($trashCan);
                checkAllDuplicates($choiceList);
                enableDisableSaveBtn();
                enableDisableCreateBtn();
            });
    } else {
        removeChoice($choice);
    }
}

$(dom.createUdfPopup).on('show.bs.modal', resetModal);

function getChanged() {
    var $deletedChoices = $(dom.udfContainer)
        .find(dom.deletedChoice)
        .find('.form-control');
    var $addedAndRenamed = $(dom.udfContainer)
        .find(dom.choiceList)
        .find('.form-control')
        .filter(function() { return !!$(this).val().trim(); })
        .filter(function() {
            var $this = $(this);
            return $this.val().trim() != $this.closest(dom.choice).data('udf-choice');
        });
    return $deletedChoices.add($addedAndRenamed);
}

// Hook for editableForm to get the data,
// since our data doesn't conform to standard fields.
function getChoiceChanges() {
    // Extract the data needed by the backend from getChanged and its dom ancestors,
    // and group the changes by the id.
    var $changed = getChanged().map(function() {
        var $el = $(this),
            $choice = $el.closest(dom.choice),
            $choiceList = $choice.closest(dom.choiceList),
            $container = $choice.closest(dom.udfContainer),
            original = $choice.data('udf-choice'),
            action = $choice.is(dom.deletedChoice) ?
                'delete' : !!original && 'rename' || 'add';

        if (action === 'delete') {
            $choiceList = $container.find(dom.choiceList);
        }
        var subfield = $choiceList.data('subfield');

        return {
            id: $container.data('udf'),
            change: {
                new_value: $el.val(),
                original_value: original,
                subfield: subfield,
                action: action
            }
        };
    });

    var changes = $changed.toArray();
    var byId = _(changes)
        .groupBy('id')
        .map(function(changes, id) {
            return {
                id: id,
                changes: _.map(changes, 'change')
            };
        })
        .value();
    return {'choice_changes': byId};
}

var stream = Bacon.mergeAll(newUdfStream, deleteResponseStream);
adminPage.init(stream);
var editForm = inlineEditForm.init({
    updateUrl: url,
    section: '#udfs',
    getDataToSave: getChoiceChanges,
    errorCallback: alerts.errorCallback,
    onSaveBefore: onSaveBefore
});
saveModal.cancelStream.onValue(editForm.cancel);

function onSaveBefore(data) {
    saveModal.show(data);
    return Bacon.once(data).flatMap(saveModal.okStream.map(data));
}

function showPutSuccess(r) {
    getChanged().each(function() {
        var $input = $(this),
            value = $input.val().trim(),
            $choice = $input.closest(dom.choice),
            original_value = $choice.data('udf-choice'),
            $container = $choice.closest(dom.udfContainer),
            $choiceList = $container.find(dom.choiceList),
            $display = $choiceList.prev(),
            $list = $display.find('ul'),
            $allDisplayItems = $list.children(dom.displayChoice),
            $item = $allDisplayItems.filter('[data-choice="' + original_value + '"]'),
            $showAllLess = $display.find(dom.showAllLess);

        // If no $item, then this is an added choice.
        // Position it before or after Show All depending on the number of elements.
        if (!$item.length) {
            $item = $(displayChoiceTemplate({
                choice: value
            }));
            $item.insertBefore($showAllLess);
        } else if ($choice.is(dom.deletedChoice)) {
            $item.remove();
        } else {
            $item.data('choice', value);
            $item.html(value);
        }
        if ($choice.is(dom.deletedChoice)) {
            $choice.remove();
        } else {
            // Set the attribute to act as a selector
            $choice.attr('data-udf-choice', value);
            // Setting the attribute doesn't update the data value
            $choice.data('udf-choice', value);
        }
    });

    toastr.success(r);
}

function restoreValues() {
    $(dom.udfs).find(dom.choiceList).each(function() {
        var $choiceList = $(this),
            $udf = $choiceList.closest(dom.udfContainer),
            $deletedChoices = $udf.find(dom.deletedChoice);

        $deletedChoices.each(function() {
            var $choice = $(this);

            $choice.prependTo($choiceList).show();
            $choice.removeData('marked');
            $choice.removeAttr('data-marked');
        });

        $choiceList.find('.duplicate-error').removeClass('duplicate-error');
        $choiceList.find('.reused-error').removeClass('reused-error');
        $choiceList.find('.blank-error').removeClass('blank-error');
        $choiceList.find('.empty-error').removeClass('empty-error');
        $choiceList.find('.whitespace-error').removeClass('whitespace-error');
        $choiceList.find('.no-double-quotes-error').removeClass('no-double-quotes-error');
        $choiceList.find('input[type="text"]').each(function() {
            var $input = $(this),
                $choice = $input.closest(dom.choice);

            $input.removeClass('error');
            if ($choice.is(dom.existingChoice)) {
                $input.val($choice.data('udf-choice'));
            } else if (0 < $choice.next().length)  {
                $choice.remove();
            }
        });

        if (0 < $deletedChoices.length) {
            // Put the choices back in their original order.
            var $display = $choiceList.prev(),
                $list = $display.find('ul'),
                $allDisplayItems = $list.children(dom.displayChoice),
                displayValues = $allDisplayItems.map(function() {
                    return $(this).data('choice');
                }).toArray(),

                $existingChoices = $choiceList.find(dom.existingChoice).detach(),
                $addNewChoice = $choiceList.find(dom.choice);

            _.each(displayValues, function(value) {
                var $choice = $existingChoices.filter('[data-udf-choice="' + value + '"]');
                $existingChoices = $existingChoices.not($choice);
                $choice.insertBefore($addNewChoice);
            });
        }
    });
}

editForm.saveOkStream.onValue(showPutSuccess);
editForm.globalCancelStream.onValue(restoreValues);
editForm.inEditModeProperty.onValue(function() {
    $(dom.saveBtn).attr('disabled', 'disabled');
});

function addNewUdf(html) {
    var $created = $(html),
        model_type = $created.data('model-type'),
        $model = $(dom.udfs).find('tbody[data-model-type="' + model_type + '"]'),
        $collections = $model.find(dom.udfContainer + '[data-is-collection="yes"]');

    if (0 < $collections.length) {
        $created.insertBefore($collections.first());
    } else {
        $created.appendTo($model);
    }
    $(dom.createUdfPopup).modal('hide');
}

function resetModal() {
    $(dom.createErrors).html('');

    // Clear input fields
    $("[data-key='udf.name']").val('');
    resetAddChoices();

    _.each([$udfType, $udfModel], function ($el) {
        $el.val($el.children().first().val());
        $el.trigger('change');
    });
}

function resetAddChoices() {
    var $addChoiceList = $(dom.addChoiceContainer).find(dom.choiceList);
    $addChoiceList.empty();
    addChoice($addChoiceList);
}

function addChoice($container) {
    var add_prefix = $container.data('add-prefix') || 'add-option-',
        num = $container.children().length + 1,
        $choice = $(choiceTemplate({
            field: add_prefix + num,
        }));
    $choice.appendTo($container);
    _.defer(function() {
        $choice.fadeIn('fast');
    });
}

function canBeSaved() {
    return 0 === $(dom.udfs).find('.form-control.error').length && 0 < getChanged().length;
}

function canBeCreated() {
    return 0 === $(dom.udfCreate).find('.form-control.error').length;
}

function enableDisableSaveBtn() {
    if (canBeSaved()) {
        $(dom.saveBtn).prop('disabled', false);
    } else {
        $(dom.saveBtn).attr('disabled', 'disabled');
    }
}

function enableDisableCreateBtn() {
    if (canBeCreated()) {
        $(dom.createNewUdf).prop('disabled', false);
    } else {
        $(dom.createNewUdf).prop('disabled', 'disabled');
    }
}

function removeChoice($choice, keep) {
    var $list = $choice.closest(dom.choiceList);
    // jQuery fadeOut doesn't actually change the dom until the fade is complete.
    // It adds a promise to the elements it is applied to,
    // which we return in case someone wants to listen for it.
    //
    // If the user cancels while the fadeOut is in progress,
    // the deleted choice will still be removed from the dom later
    // when the fadeOut is done. Simplest way to avoid this race
    // is to disable Cancel until the fadeOut is complete.
    $(dom.cancelBtn).attr('disabled', 'disabled');
    return $choice.fadeOut('fast')
        .promise().then(function () {
            if (keep) {
                $choice.detach();
                // No point in checking duplicates until after the caller
                // does something with the $choice it wants to keep.
            } else {
                $choice.remove();
                checkAllDuplicates($list);
                enableDisableSaveBtn();
                enableDisableCreateBtn();
            }
            $(dom.cancelBtn).prop('disabled', false);
        });
}

resetAddChoices();

function getNewUdfParams() {
    var fields = _($('[data-key]').toArray())
            .map($)
            .reduce(function(values, $element) {
                values[$element.data('key')] = $element.val();
                return values;
            }, {});

    fields['udf.choices'] = getChoices($(dom.addChoiceContainer));

    return fields;
}

function getChoices($choiceList, $except) {
    $except = $except || $();
    var $choices = $choiceList.find(dom.choice).not($except);
    // _.compact removes empty values, including the "Add a new" placeholder option
    return _.compact(_.map($choices, function (element) {
        return $(element).find('input[type="text"]').val();
    }));
}

function validate($choiceList, $choice, $input) {
    var isMultiple = false;
    if (1 === $choice.closest(dom.addChoiceContainer).length) {
        isMultiple = $udfType.val() === 'multichoice';
    } else {
        isMultiple = $choice.closest(dom.udfContainer).data('datatype') === 'multichoice';
    }
    $choice.toggleClass('no-double-quotes-error',
        isMultiple && -1 < $input.val().indexOf('"'));

    if (0 === $input.val().length && !!$choice.data('udf-choice')) {
        $choice.toggleClass('blank-error', true);
    } else if ($choice.is(':only-child') ||
        ($choice.is(':first-child:not(' + dom.existingChoice + ')') && $input.val() === '')) {
        $choice.toggleClass('empty-error', true);
    } else if ($input.val() !== $input.val().trim()) {
        $choice.toggleClass('whitespace-error', true);
    } else {
        $choice.toggleClass('blank-error', false);
        $choice.toggleClass('empty-error', false);
        $choice.toggleClass('whitespace-error', false);
    }
}

// For use in jQuery filters
function trimOrNull(value) {
    return !!value ? value.toString().trim() : null;
}
function getValue(choiceElem) {
    var value = $(choiceElem).find('.form-control').val();
    return trimOrNull(value);
}
function compact(index, elem) {
    return !!getValue($(elem));
}
function getOriginalValue(choiceElem) {
    return trimOrNull($(choiceElem).data('udf-choice'));
}
function compactOriginal(index, elem) {
    return !!getOriginalValue($(elem));
}

function checkDuplicates($choiceList, $choice) {
    // There are two kinds of duplication.
    // There's the obvious duplication where the values
    // of two or more text input boxes are the same,
    // and then there's the less obvious duplication
    // when the value of one or more text input boxes
    // is the same as the original value of some other
    // modified text input box corresponding to an existing
    // choice in an existing udf.
    //
    // The latter is invalid because in order to permit it,
    // the code would have to do cycle detection,
    // which is more complexity than is wanted here.
    // It's not a hardship to require the user to do a Save
    // after a rename before renaming another choice to
    // the original name of the first.

    var $otherChoices = $choiceList.find(dom.choice).not($choice),
        choiceValue = getValue($choice),
        isDuplicate = function(testValue) {
            return function(index, choiceElem) {
                return getValue($(choiceElem)) === testValue;
            };
        };

    // clear duplicate-errors and recalculate them
    $otherChoices.add($choice).removeClass('duplicate-error');

    var $duplicates = !!choiceValue && $otherChoices.filter(isDuplicate(choiceValue)) || [];

    // Flag duplication on the $choice if it isn't in the trash can
    if (0 === $choice.closest(dom.trashCan).length && 0 < $duplicates.length) {
        $duplicates.add($choice).toggleClass('duplicate-error', true);
    }
    // Invalidate other choices if they duplicate $choice
    $otherChoices.filter(compact).each(function() {
        var $other = $(this),
            otherValue = getValue($other),
            $otherChoices = $choiceList.find(dom.choice).not($other).filter(compact),
            $duplicates = $otherChoices
                .filter(isDuplicate(otherValue))
                .filter(function() {
                    return 0 === $(this).closest(dom.trashCan).length;
                });
        if (0 < $duplicates.length) {
            $duplicates.add($other).toggleClass('duplicate-error', true);
        }
    });

    // Invalidate $choice if it reuses another choice
    var $udf = $choiceList.closest(dom.udfContainer),
        $trashCan = $udf.find(dom.trashCan),
        $trashedChoices = $trashCan.find(dom.choice),
        // The value of $choice can only match 0 or 1 other original value.
        $matchedOriginal = $otherChoices.add($trashedChoices).filter(function() {
            var originalValue = getOriginalValue($(this));
            return originalValue ? originalValue === choiceValue : false;
        });
    $choice.toggleClass('reused-error', 0 < $matchedOriginal.length);

    $trashedChoices.find('.form-control').toggleClass('error', false);
    highlightErrors($choiceList);
}

function highlightErrors($choiceList) {
    // highlight the associated form controls
    $choiceList.find('.form-control').toggleClass('error', false);
    $choiceList.find('.duplicate-error .form-control')
        .toggleClass('error', true);
    $choiceList.find('.reused-error .form-control')
        .toggleClass('error', true);
    $choiceList.find('.blank-error .form-control')
        .toggleClass('error', true);
    $choiceList.find('.empty-error .form-control')
        .toggleClass('error', true);
    $choiceList.find('.whitespace-error .form-control')
        .toggleClass('error', true);
    $choiceList.find('.no-double-quotes-error .form-control')
        .toggleClass('error', true);
}

function checkAllDuplicates($choiceList) {
    var $udf = $choiceList.closest(dom.udfContainer),
        $trashCan = $udf.find(dom.trashCan);

    // Need to validate against the $trashCan as well,
    // in order to remove duplicates that no longer matter
    // and expose reuse of trashed choices.
    $choiceList.add($trashCan).find(dom.choiceInput).each(function(i, input) {
        var $input = $(input),
            $choice = $input.closest(dom.choice);
        validate($choiceList, $choice, $input);
        checkDuplicates($choiceList, $choice, $input);
    });
}
