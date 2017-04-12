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
    // "Remove Choice" button on "Remove field choice" modal
    removeChoiceAction: '[data-udf-action="delete"]',

    choices: '.choice-udf-choices',
    existingChoice: '[data-udf-choice]',
    addChoiceContainer: '#udf-create-choices',
    duplicateError: '[data-item="duplicate"]',
    reusedError: '[data-item="reused"]',
    blankError: '[data-item="blank"]',
    popupTarget: '[data-popup-target]',
    originalChoice: '[data-original-choice]',
    displayChoice: '[data-choice]',
    showAllLess: '[data-less-more]',
    saveModal: '#save-udf-panel',
    saveConfirm: '[data-action="save"]',

    udfs: '#udf-info',

    saveBtn: '.saveBtn',

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
                // TODO: The new choice item is not up to spec.
                // It should read "Choice XX", where XX is the numeric index of
                // the choice, and the word "Choice" should be translated.
                var displayOriginal = changeSpec.original_value || 'new choice';
                return saveConfirmChangeTemplate({
                    originalValue: displayOriginal,
                    newValue: changeSpec.new_value
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
    var showChoices = _.contains(['choice', 'multichoice'], $(e.currentTarget).val());
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
        if (0 === $(dom.udfs).find('.form-control.error').length) {
            $(dom.saveBtn).removeAttr('disabled');
        } else {
            $(dom.saveBtn).attr('disabled', 'disabled');
        }
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

    if ($button.is(dom.popupTarget)) {
        presentRemoveChoicePopup($button, $choice);
    } else {
        removeChoice($choice);
    }
});

// dom.removeChoiceAction is what the user clicks to affirm that
// they really want to delete the choice.
$(dom.removeChoiceAction)
    .asEventStream('click')
    .map('.target')
    .map($)
    .onValue(function($removeControl) {
        var options = JSON.parse($removeControl.data('remove-choice-info'));
        $.ajax({
            method: 'PUT',
            url: getUdfUrlForId(options.id),
            contentType: 'application/json',
            data: JSON.stringify({
                'original_value': options.choice,
                'subfield': options.subfield,
                'new_value': '',
                'action': 'delete'
            })
        }).done(function (r) {
            var $container = $('[data-udf="' + options.id + '"]'),
                $display = $container.find('[data-class="display"]'),
                $choiceList = $container.find('[data-class="edit"]'),
                $choice = $choiceList.find('[data-udf-choice="' + options.choice + '"]'),
                $item = $display.find('[data-choice="' + options.choice + '"]');

            $item.remove();

            toastr.success(r);
            removeChoice($choice);
        }).fail(function (resp) {
            var vals = _.values(JSON.parse(resp.responseText));

            toastr.error(
                '<ul><li>' + vals.join('</li><li>') + '</li></ul>');
        });
    });

function presentRemoveChoicePopup($trashButton, $choice) {
    var $choiceList = $choice.closest(dom.choiceList);

    var $udfpopup = $($trashButton.data('popup-target'));
    var $action = $udfpopup.find(dom.removeChoiceAction);

    $action.data('remove-choice-info', JSON.stringify({
        'id': $choiceList.closest(dom.udfContainer).data('udf'),
        'subfield': $choiceList.data('subfield'),
        'choice': $choice.data('udf-choice')
    }));

    $udfpopup.modal('show');
}

$(dom.createUdfPopup).on('show.bs.modal', resetModal);

function getChanged() {
    return $(dom.udfContainer)
        .find(dom.choiceList)
        .find('.form-control')
        .filter(function() { return !!$(this).val().trim(); })
        .filter(function() {
            var $this = $(this);
            return $this.val().trim() != $this.closest(dom.choice).data('udf-choice');
        });
}

// Hook for editableForm to get the data,
// since our data doesn't conform to standard fields.
function getChoiceChanges() {
    var $changed = getChanged(),
        // Extract the data needed by the backend from
        // $changed and its dom ancestors.
        idChange = _.map($changed.toArray(), function(el) {
            var $el = $(el),
                $choice = $el.closest(dom.choice),
                $choiceList = $choice.closest(dom.choiceList),
                $container = $choiceList.closest(dom.udfContainer),
                original = $choice.data('udf-choice'),
                subfield = $choiceList.data('subfield');

            return {
                id: $container.data('udf'),
                change: {
                    new_value: $el.val(),
                    original_value: original,
                    subfield: subfield,
                    action: !!original && 'rename' || 'add'
                }
            };
        }),
        // Group the changes by the id
        byId = _.chain(idChange)
            .groupBy('id')
            .map(function(changes, id) {
                return {
                    id: id,
                    changes: _.pluck(changes, 'change')
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
            $choiceList = $choice.closest(dom.choiceList),
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
        } else {
            $item.data('choice', value);
            $item.html(value);
        }
        // Set the attribute to act as a selector
        $choice.attr('data-udf-choice', value);
        // Setting the attribute doesn't update the data value
        $choice.data('udf-choice', value);
        $choice.find(dom.choiceDelete).attr('data-popup-target', '#remove-udf-choice-panel');
    });

    toastr.success(r);
}

function restoreValues() {
    $(dom.udfs).find(dom.choiceList).each(function() {
        var $choiceList = $(this);

        $choiceList.find('.duplicate-error').removeClass('duplicate-error');
        $choiceList.find('.reused-error').removeClass('reused-error');
        $choiceList.find('.blank-error').removeClass('blank-error');
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
    });
}

editForm.saveOkStream.onValue(showPutSuccess);
editForm.globalCancelStream.onValue(restoreValues);
editForm.inEditModeProperty.onValue(function() {
    $(dom.saveBtn).attr('disabled', 'disabled');
});

function addNewUdf(html) {
    var $created = $(html),
        $model = $(dom.udfs).find('[data-model-type="' + $created.data('model-type') + '"]'),
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
        $el.change();
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

function removeChoice($choice) {
    var $list = $choice.closest(dom.choiceList);
    $choice.fadeOut('fast', function() {
        $choice.remove();
        checkAllDuplicates($list);
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
    if (0 === $input.val().length && !!$choice.data('udf-choice')) {
        $choice.toggleClass('blank-error', true);
    } else {
        $choice.toggleClass('blank-error', false);
    }
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
        getValue = function(choiceElem) {
            var value = $(choiceElem).find('.form-control').val();
            return !!value ? value.trim() : null;
        },
        choiceValue = getValue($choice),
        getOriginalValue = function(choiceElem) {
            var value = $(choiceElem).data('udf-choice');
            return !!value ? value.trim() : null;
        },
        isDuplicate = function(testValue) {
            return function(index, choiceElem) {
                return getValue($(choiceElem)) === testValue;
            };
        };

    var $duplicates = !!choiceValue && $otherChoices.filter(isDuplicate(choiceValue)) || [],
        // The value of $choice can only match 0 or 1 other original value.
        $matchedOriginal = $otherChoices.filter(function() {
            var originalValue = getOriginalValue($(this));
            return originalValue ? originalValue === choiceValue : false;
        });

    if (0 < $duplicates.length) {
        $duplicates.add($choice).toggleClass('duplicate-error', true);
    }
    // clear duplicate-errors and recalculate them
    $otherChoices.add($choice).removeClass('duplicate-error');
    var compact = function(index, elem) {
        return !!getValue($(elem));
    };
    $otherChoices.filter(compact).each(function() {
        var $other = $(this),
            otherValue = getValue($other),
            $otherChoices = $choiceList.find(dom.choice).not($other).filter(compact),
            $duplicates = $otherChoices.filter(isDuplicate(otherValue));
        if (0 < $duplicates.length) {
            $duplicates.add($other).toggleClass('duplicate-error', true);
        }
    });
    $choice.toggleClass('reused-error', 0 < $matchedOriginal.length);
    // highlight the associated form controls
    $choiceList.find('.form-control').toggleClass('error', false);
    $choiceList.find('.duplicate-error .form-control')
        .toggleClass('error', true);
    $choiceList.find('.reused-error .form-control')
        .toggleClass('error', true);
    $choiceList.find('.blank-error .form-control')
        .toggleClass('error', true);
}

function checkAllDuplicates($choiceList) {
    $choiceList.find(dom.choiceInput).each(function(i, input) {
        var $input = $(input),
            $choice = $input.closest(dom.choice);
        validate($choiceList, $choice, $input);
        checkDuplicates($choiceList, $choice, $input);
    });
}
