"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    toastr = require('toastr'),
    BU = require('treemap/lib/baconUtils.js'),
    U = require('treemap/lib/utility.js'),
    buttonEnabler = require('treemap/lib/buttonEnabler.js'),
    errors = require('manage_treemap/lib/errors.js'),
    simpleEditForm = require('treemap/lib/simpleEditForm.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

var dom = {
    selects: 'select[data-name]',
    radios: ':radio:checked[data-name]',
    roleIds: '[data-roles]',
    createNewRole: '#create_new_role',
    newRoleName: '#new_role_name',
    roles: '#role-info',
    edit: '.editBtn',
    save: '.saveBtn',
    cancel: '.cancelBtn',
    addRole: '.addRoleBtn',
    addRoleModal: '#add-role-modal',
    spinner: '.spinner',
    rolesTableContainer: '#role-info .role-table-scroll',
    newFieldsAlert: '#new-fields-alert',
    newFieldsDismiss: '#new-fields-dismiss'
};

var url = reverse.roles_endpoint(config.instance.url_name),
    updateStream = $(dom.save)
        .asEventStream('click')
        .doAction(function(e) {
            e.preventDefault();
            $(dom.spinner).show();
            $(dom.save).prop("disabled", true);
        })
        .map(getRolePermissions)
        .flatMap(BU.jsonRequest('PUT', url));

simpleEditForm.init({
    edit: dom.edit,
    cancel: dom.cancel,
    save: dom.save,
    saveStream: updateStream
});

function enableSave() {
    $(dom.spinner).hide();
    $(dom.save).prop("disabled", false);
}

function showError(resp) {
    enableSave();
    toastr.error(resp.responseText);
}

updateStream.onError(showError);

updateStream.onValue(enableSave);

buttonEnabler.run();
U.modalsFocusOnFirstInputWhenShown();
$(dom.addRole).on('click', function () {
    $(dom.addRoleModal).modal('show');
});

var newRoleStream = $(dom.createNewRole)
    .asEventStream('click')
    .doAction(function () { $(dom.spinner).show(); })
    .map($(dom.newRoleName))
    .map('.val')
    .flatMap(getNewRoleHtml(url));

newRoleStream.onError(showError);

newRoleStream
    .onValue(addNewRole);

var alertDismissStream = $(dom.newFieldsDismiss).asEventStream('click')
    .doAction('.preventDefault')
    .map(undefined)
    .flatMap(BU.jsonRequest('POST', $(dom.newFieldsDismiss).attr('href')));

alertDismissStream.onValue(function() {
    $(dom.newFieldsAlert).hide();
    $(dom.roles).find('tr.active').removeClass('active');
});

adminPage.init(Bacon.mergeAll(updateStream, alertDismissStream));

function getRolePermissions() {
    var roleIds = $(dom.roleIds).data('roles').split(',');
    var roles = _.zipObject(roleIds, _.times(roleIds.length, function () {
        return {
            'fields': {}, 'models': {}
        };
    }));
    $(dom.selects).each(function(i, select) {
        var $select = $(select);
        var roleId = $select.attr('data-role-id');
        var field = $select.attr('data-name');
        var perm = $select.val();

        roles[roleId].fields[field] = perm;
    });
    $(dom.radios).each(function(i, radio) {
        var $radio = $(radio),
            roleId = $radio.data('role-id'),
            permissionName = $radio.data('name'),
            hasPermission = $radio.data('value');
        roles[roleId].models[permissionName] = hasPermission;
    });

    return roles;
}

function createRoleOptionElement(role) {
    return $('<option>')
        .attr('value', role)
        .html(role);
}

function addNewRole(html) {
    $(dom.spinner).hide();

    $(dom.newRoleName).val('');

    $(dom.roles).html(html);
    // Scroll over to the new role for easier editing of it
    $(dom.rolesTableContainer).animate({scrollLeft: $(dom.rolesTableContainer)[0].scrollWidth});
}

function getNewRoleHtml(url) {
    return function(role) {
        var req = $.ajax({
            url: url,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({'name': role})
        });

        return Bacon.fromPromise(req);
    };
}
