"use strict";

var $ = require('jquery'),
    _ = require('lodash'),

    _circumferenceSelector = '[data-class="circumference-input"]',
    _diameterSelector = '[data-class="diameter-input"]',
    _addRowBtnSelector = '#add-trunk-row',
    _tbodySelector = '#diameter-worksheet',
    _trunkRowSelector = '#trunk-row',
    _totalRowSelector = '#diameter-calculator-total-row',
    _totalReferenceSelector = '#diameter-calculator-total-reference',
    _totalFieldSelector = 'input[name="tree.diameter"]',
    _diameterFieldSelector = '[data-field="tree.diameter"]';

function eventToText(e) {
    return $(e.target).val();
}

function elementToValue(el) {
    return $(el).data('value');
}

function textToFloat(t) {
    var f = parseFloat(t);

    return isValidNumber(f) ? f : 0;
}

function isValidNumber(num) {
    return _.isNumber(num) && !isNaN(num);
}

function diameterToCircumference(diameter) {
    return diameter * Math.PI;
}

function circumferenceToDiameter(circumference) {
    return circumference / Math.PI;
}

function toFixed(value, $parentForm) {
    if (! _.isNumber(value)) {
        return value;
    }
    var $field = $parentForm.find(_diameterFieldSelector).first(),
        digits = $field.data('digits');
    return value.toFixed(digits);
}

function calculateDiameterFromMultiple(diameters) {
    if (diameters.length === 0) {
        return '';
    }
    // this formula is a shortcut for:
    // 1) calculate area of each diameter
    // 2) add the areas together
    // 3) derive the diamater from this aggregrate trunk
    var squares = _.map(diameters, function (x) { return x * x; }),
        summedSquares = _.reduce(squares, function (x, y) { return x + y; }, 0),
        totalDiameter = Math.sqrt(summedSquares);

    // Above method will make total diameter positive even if there are negative values.
    // We'd rather they be reported as negative and show error validation
    if (_.some(diameters, function(d) { return d < 0; })) {
        totalDiameter = -totalDiameter;
    }

    return totalDiameter;
}

function getDiameter ($parentForm) {
    return $parentForm.find(_totalFieldSelector).val();
}

function init ($parentForm, diameter) {
    var $trunkRow = $parentForm.find(_trunkRowSelector),
        $totalRow = $parentForm.find(_totalRowSelector),
        $totalReference = $parentForm.find(_totalReferenceSelector),
        $singleDiameterEntryField = $trunkRow.find(_diameterSelector),
        $singleCircumferenceEntryField = $trunkRow.find(_circumferenceSelector);

    if (diameter) {
        var diameterDisplay = toFixed(textToFloat(diameter), $parentForm);
        $totalReference.html(diameterDisplay);
        $singleDiameterEntryField.val(diameterDisplay);
        $singleCircumferenceEntryField
            .val(toFixed(diameterToCircumference(diameter), $parentForm));
    }
    $totalRow.hide();

    // delete additional rows that were added to the worksheet
    // for multiple trunks, resetting to just the initial row
    // used for single trunks
    $parentForm
        .find(_tbodySelector)
        .find('tr')
        .not(_trunkRowSelector)
        .remove();
}

function updateTotalDiameter ($parentForm) {
    // update the readonly total field that gets written
    // to the db with the values from the worksheet
    var $diameterFields = $parentForm.find(_diameterSelector),
        $totalField = $parentForm.find(_totalFieldSelector),
        $totalReference = $parentForm.find(_totalReferenceSelector),
        diameterValues = _.map($diameterFields, elementToValue),
        validValues = _.filter(diameterValues, isValidNumber),
        totalDiameter = calculateDiameterFromMultiple(validValues);

    $totalReference.html(toFixed(totalDiameter, $parentForm));
    $totalField.val(totalDiameter);
}

function createWorksheetRow ($parentForm) {
    // add a worksheet row to the dom with diameter
    // and circumference fields that automatically
    // update each other.
    //
    // uses the existing, single trunk row as a template
    // for additional rows. This was designed this way so
    // that the serverside template can populate the initial
    // single trunk row, which is the most common use case
    // rather than building the whole thing with javascript.
    var $tbody = $parentForm.find(_tbodySelector),
        $templateTr = $tbody.find(_trunkRowSelector),
        html = $templateTr.html(),
        $newEl = $('<tr>').append(html),
        $circEl = $newEl.find(_circumferenceSelector),
        $diamEl = $newEl.find(_diameterSelector),
        $totalRow = $(_totalRowSelector);

    $diamEl.val('');
    $circEl.val('');
    $tbody.append($newEl);

    // when a row is added, show the total row.
    // it will remain visible until this module is re-initialized.
    $totalRow.show();
}

function updateRowValues ($parentForm, event) {
    // when diameter or circumference is changed: compute the other value,
    // store both values in "data-value" attributes, display a fixed
    // point version of the other value, and update the readonly total field.
    var $eventTarget = $(event.target),
        isDiameter = $eventTarget.is(_diameterSelector),
        isCircumference = $eventTarget.is(_circumferenceSelector),
        conversionFn = isDiameter ?
            diameterToCircumference : circumferenceToDiameter,
        selector = isDiameter ?
            _circumferenceSelector : _diameterSelector;

    if (isDiameter || isCircumference) {
        var textValue = eventToText(event),
            value, otherValue, otherValueDisplay;

        if (textValue.trim() === '') {
            value = '';
            otherValue = '';
            otherValueDisplay = '';
        } else {
            value = textToFloat(textValue);
            otherValue = conversionFn(value);
            otherValueDisplay = toFixed(otherValue, $parentForm);
        }

        $eventTarget
            .data('value', value)
            .closest('tr')
            .find(selector)
            .data('value', otherValue)
            .val(otherValueDisplay);
        updateTotalDiameter($parentForm);
    }
}


exports = module.exports = function diameterCalculator (options) {
    var formSelector = options.formSelector,
        $parentForm = $(formSelector),
        initialDiameter = getDiameter($parentForm),

        unsubscribeCancel = options.cancelStream
            .onValue(init, $parentForm, initialDiameter),

        unsubscribeOk = options.saveOkStream
            .onValue(function () {
                initialDiameter = getDiameter($parentForm);
                init($parentForm, initialDiameter);
            });

    $parentForm.find(_tbodySelector).on('input', 'input',
                         _.partial(updateRowValues, $parentForm));

    $parentForm.find(_addRowBtnSelector).on('click',
        _.partial(createWorksheetRow, $parentForm));

    init($parentForm, initialDiameter);

    return {
        destroy: function () {
            unsubscribeCancel();
            unsubscribeOk();
            $(_tbodySelector).off('input');
            $(_addRowBtnSelector).off('click');
        }
    };

};
