"use strict";

var $ = require('jquery'),
    R = require('ramda'),
    FH = require('treemap/lib/fieldHelpers.js');

require('treemap/lib/baconUtils.js');

exports.init = function(options) {
    var inEditModeProperty = options.form.inEditModeProperty,
        $addTreeControls = $(options.addTreeControls),
        $beginAddTree = $(options.beginAddTree),
        beginAddStream = $beginAddTree.asEventStream('click'),
        enterEditModeStream = inEditModeProperty.filter(R.equals(true)),
        exitEditModeStream = inEditModeProperty.filter(R.equals(false));

    function updateForm (val) {
        var $editFields = $('[data-class="edit"]');
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
