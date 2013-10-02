// Helper functions for fields defined by the field.html template

"use strict";

var $ = require('jquery'),
    _ = require('underscore');

var getField = exports.getField = function ($fields, name) {
    return $fields.filter('[data-field="' + name + '"]');
};

exports.getSerializableField = function ($fields, name) {
    // takes a jQuery collection of edit fields and returns the
    // actual input or select field that will be serialized
    return getField($fields, name).find('[name="' + name + '"]');
};

exports.formToDictionary = function ($form, $editFields) {
    var isTypeaheadHiddenField = function(name) {
        return $form.find('[name="' + name + '"]').is('[data-typeahead-hidden]');
    };
    var result = {};
    _.each($form.serializeArray(), function(item) {
        var type = exports.getField($editFields, item.name).data('type');
        if (type === 'bool'){
            return;
        } else if (item.value === '' && (type === 'int' || type === 'float')) {
            // convert empty numeric fields to null
            result[item.name] = null;
        } else if (item.value === '' && isTypeaheadHiddenField(item.name)) {
            // convert empty foreign key id strings to null
            result[item.name] = null;
        } else {
            result[item.name] = item.value;
        }
    });
    $form.find('input[name][type="checkbox"]').each(function() {
        result[this.name] = this.checked;
    });
    return result;
};
