"use strict";

var $ = require('jquery'),
    R = require('ramda'),
    Bacon = require('baconjs'),
    FH = require('treemap/fieldHelpers');

require('treemap/baconUtils');

exports.init = function(options) {
    var inEditModeProperty = options.form.inEditModeProperty,
        $addTreeControls = $(options.addTreeControls),
        $beginAddTree = $(options.beginAddTree),
        beginAddStream = $beginAddTree.asEventStream('click'),
        enterEditModeStream = inEditModeProperty.filter(R.eq(true)),
        exitEditModeStream = inEditModeProperty.filter(R.eq(false));

    function updateForm (val) {
        var $editFields = $(options.inlineEditForm.editFields);
        FH.getSerializableField($editFields, 'tree.plot').val(val);
    }

    function enterInitialReadState () {
        $addTreeControls.hide();
        $beginAddTree.hide();
        updateForm('');
    }

    function enterInitialEditState () {
        $addTreeControls.show();
        $beginAddTree.show();
        updateForm('');
    }

    function enterActiveEditState () {
        $addTreeControls.show();
        $beginAddTree.hide();
        updateForm(options.plotId);
    }

    beginAddStream.onValue(enterActiveEditState);

    enterEditModeStream.onValue(enterInitialEditState);
    exitEditModeStream.onValue(enterInitialReadState);

    return beginAddStream;
};
