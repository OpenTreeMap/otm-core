"use strict";

var $ = require('jquery'),
    _ = require('underscore'),

    circumferenceSelector = '[data-class="circumference-input"]',
    diameterSelector = '[data-class="diameter-input"]',
    addRowBtnSelector = '#add-trunk-row',
    tbodySelector = '#diameter-worksheet',
    trunkRowSelector = '#trunk-row',
    totalFieldSelector = 'input[name="tree.diameter"]';


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

function createWorksheetRow () {
    // add a worksheet row to the dom
    var $tbody = $(tbodySelector),
        $templateTr = $tbody.find(trunkRowSelector),
        html = $templateTr.html(),
        $newEl = $('<tr>').append(html),
        $circEl = $newEl.find(circumferenceSelector),
        $diamEl = $newEl.find(diameterSelector);

    $diamEl.val('');
    $circEl.val('');
    $tbody.append($newEl);
}

function updateTotalDiameter () {
    // update the readonly total field that gets written
    // to the db with the values from the worksheet
    var $diameterFields = $(diameterSelector),
        $totalField = $(totalFieldSelector),
        diameterValues = _.map($diameterFields,
                               _.compose(textToFloat, elementToText)),
        validValues = _.reject(diameterValues, isNaN),
        totalDiamater = calculateDiameterFromMultiple(validValues);

    $totalField.val(totalDiamater);
}

function updateCorrespondingRowValue (event) {
    // when a worksheet row is modified, update the corresponding 
    // circ/diam as well, and finally, update the readonly total field
    var $eventTarget = $(event.target),
        isDiameter = $eventTarget.is(diameterSelector),
        isCircumference = $eventTarget.is(circumferenceSelector),
        conversionFn = isDiameter ?
            diameterToCircumference : circumferenceToDiameter,
        selector = isDiameter ?
            circumferenceSelector : diameterSelector,
        transFn = _.compose(zeroToEmptyString, conversionFn,
                            textToFloat, eventToText);

    if (isDiameter || isCircumference) {
        $eventTarget
            .closest('tr')
            .find(selector)
            .val(transFn(event));
        updateTotalDiameter();
    }
}

exports.init = function(options) {
    $(tbodySelector).on('input', 'input', updateCorrespondingRowValue);
    $(addRowBtnSelector).click(createWorksheetRow);
};
