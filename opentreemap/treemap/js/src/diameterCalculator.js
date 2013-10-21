"use strict";

var $ = require('jquery'),
    _ = require('underscore'),

    _circumferenceSelector = '[data-class="circumference-input"]',
    _diameterSelector = '[data-class="diameter-input"]',
    _addRowBtnSelector = '#add-trunk-row',
    _tbodySelector = '#diameter-worksheet',
    _trunkRowSelector = '#trunk-row',
    _totalRowSelector = '#diameter-calculator-total-row',
    _totalReferenceSelector = '#diameter-calculator-total-reference',
    _totalFieldSelector = 'input[name="tree.diameter"]';

function eventToText(e) {
    return $(e.target).val();
}

function elementToText(el) {
    return $(el).val();
}

function zeroToEmptyString(n) {
    return n === 0 ? '' : n;
}

function textToFloat(t) {
    var f = parseFloat(t);

    return isNaN(f) ? 0 : f;
}

function diameterToCircumference(diameter) {
    return diameter * Math.PI;
}

function circumferenceToDiameter(circumference) {
    return circumference / Math.PI;
}

function calculateDiameterFromMultiple(diameters) {
    // this formula is a shortcut for:
    // 1) calculate area of each diameter
    // 2) add the areas together
    // 3) derive the diamater from this aggregrate trunk
    var squares = _.map(diameters, function (x) { return x * x; }),
        summedSquares = _.reduce(squares, function (x, y) { return x + y; }, 0),
        totalDiameter = Math.sqrt(summedSquares);

    return totalDiameter;
}

function getDiameter ($parentForm) {
    return $parentForm.find(_totalFieldSelector).val();
}

function reset ($parentForm, initialDiameter) {
    var $trunkRow = $parentForm.find(_trunkRowSelector),
        $totalField = $parentForm.find(_totalFieldSelector),
        $singleDiameterEntryField = $trunkRow.find(_diameterSelector),
        $singleCircumferenceEntryField = $trunkRow.find(_circumferenceSelector);

    $totalField.val(initialDiameter);

    $singleDiameterEntryField.val(initialDiameter);

    $singleCircumferenceEntryField
        .val(diameterToCircumference(initialDiameter));

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
        diameterValues = _.map($diameterFields,
                               _.compose(textToFloat, elementToText)),
        validValues = _.reject(diameterValues, isNaN),
        totalDiameter = calculateDiameterFromMultiple(validValues);

    $totalReference.html(totalDiameter);
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

    // when a row is added, make the total row visible.
    // it will remain visible thereafter.
    $totalRow.css('visibility', 'visible');
}

function updateCorrespondingRowValue ($parentForm, event) {
    // when a worksheet row is modified, update the corresponding 
    // circ/diam as well, and finally, update the readonly total field
    var $eventTarget = $(event.target),
        isDiameter = $eventTarget.is(_diameterSelector),
        isCircumference = $eventTarget.is(_circumferenceSelector),
        conversionFn = isDiameter ?
            diameterToCircumference : circumferenceToDiameter,
        selector = isDiameter ?
            _circumferenceSelector : _diameterSelector,
        transFn = _.compose(zeroToEmptyString, conversionFn,
                            textToFloat, eventToText);

    if (isDiameter || isCircumference) {
        $eventTarget
            .closest('tr')
            .find(selector)
            .val(transFn(event));
        updateTotalDiameter($parentForm);
    }
}


exports = module.exports = function diameterCalculator (options) {
    var formSelector = options.formSelector,
        $parentForm = $(formSelector),
        initialDiameter = getDiameter($parentForm),

        unsubscribeCancel = options.cancelStream
            .onValue(reset, $parentForm, initialDiameter),

        unsubscribeOk = options.saveOkStream
            .onValue(function () {
                initialDiameter = getDiameter($parentForm);
                reset($parentForm, initialDiameter);
            });

    $parentForm.find(_tbodySelector).on('input', 'input',
                         _.partial(updateCorrespondingRowValue,
                                   $parentForm));

    $parentForm.find(_addRowBtnSelector).click(
        _.partial(createWorksheetRow, $parentForm));


    return {
        destroy: function () {
            unsubscribeCancel();
            unsubscribeOk();
            $(_tbodySelector).off('input');
            $(_addRowBtnSelector).off('click');
        }
    };

};
