"use strict";

var $ = require('jquery'),
    toastr = require('toastr'),
    Bacon = require('baconjs'),
    BU = require('treemap/lib/baconUtils.js'),
    errors = require('manage_treemap/lib/errors.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    simpleEditForm = require('treemap/lib/simpleEditForm.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

var dom = {
    form: '#user-roles',
    container: '#user-roles-content',

    addUser: '#invite-user',
    addUserModal: '#add-user-modal',
    addUserEmail: '#user-email',
    addUserErrors: '#add-user-errors',

    edit: '#user-roles .editBtn',
    save: '#user-roles .saveBtn',
    cancel: '#user-roles .cancelBtn',
    spinner: '#user-roles .spinner',

    invited: '#invite-role-list',
    users: '#user-role-list',

    pagingControls: '.pagination a',
    sortingControls: '[data-sort] a',
    searchControl: '#user-search',
    searchUrl: '#search-url',
    clearSearch: '#clear-search',

    removeInvite: '#remove-invite',
    removeInviteModal: '#remove-invite-modal'
};

adminPage.init();

var url = reverse.user_roles(config.instance.url_name),
    $container = $(dom.container),
    $addUser = $(dom.addUser),
    $addUserModal = $(dom.addUserModal),
    $addUserEmail = $(dom.addUserEmail),
    $addUserErrors = $(dom.addUserErrors),
    $removeInviteModal = $(dom.removeInviteModal);

$(dom.edit).on('click', disableControls);
$(dom.cancel).on('click', enableControls);

var updateStream = $(dom.save)
    .asEventStream('click')
    .doAction(function(e) {
        e.preventDefault();
        showSpinner();
        $(dom.save).prop("disabled", true);
    })
    .map(getUpdatedUserRoles)
    .flatMap(BU.jsonRequest('PUT', url));

function disableControls() {
    function disable(i, elem) {
        var $elem = $(elem);
        if ($elem.parent().is(':not(.disabled,.active)')) {
            $elem.data('href', $elem.attr('href'));
            $elem.removeAttr('href');
            $elem.parent().addClass('disabled');
        }
    }
    $container.find(dom.pagingControls).each(disable);
    $container.find(dom.sortingControls).each(disable);
    $(dom.searchControl).prop('disabled', true);
    $(dom.clearSearch).prop('disabled', true);
}

function enableControls() {
    function enable(i, elem) {
        var $elem = $(elem);
        if ($elem.data('href')) {
            $elem.attr('href', $elem.data('href'));
            $elem.parent().removeClass('disabled');
        }
    }
    $container.find(dom.pagingControls).each(enable);
    $container.find(dom.sortingControls).each(enable);
    $(dom.searchControl).prop('disabled', false);
    $(dom.clearSearch).prop('disabled', false);
}

function enableSave() {
    hideSpinner();
    $(dom.save).prop("disabled", false);
}

function showError(resp) {
    enableSave();
    toastr.error(resp.responseText);
}

function showSpinner() {
    $(dom.spinner).show();
}

function hideSpinner() {
    $(dom.spinner).hide();
}

updateStream.onError(showError);

updateStream.onValue(enableSave);
updateStream.onValue(enableControls);

simpleEditForm.init({
    edit: dom.edit,
    cancel: dom.cancel,
    save: dom.save,
    saveStream: updateStream
});

var addStream = $addUser
    .asEventStream('click')
    .map(function () {
        return {'email': $addUserEmail.val()};
    })
    .flatMap(BU.jsonRequest('POST', url));

addStream.onValue(function(response) {
    $container.html(response);
    $addUserModal.modal('hide');
});

$addUserModal.on('hidden.bs.modal', function() {
    $addUserEmail.val('');
    $addUserErrors.html('');
});

addStream
    .errors()
    .mapError(errors.convertErrorObjectIntoHtml)
    .onValue($addUserErrors, 'html');

var searchStream = $(dom.searchControl)
    .asEventStream('keypress')
    .filter(BU.isEnterKey);

var resetSearchStream = $(dom.clearSearch)
    .asEventStream('click')
    .doAction('.preventDefault')
    .doAction($(dom.searchControl), 'val', '');

var searchResponseStream = Bacon.mergeAll(searchStream, resetSearchStream)
    .map(function() {
        return $(dom.searchUrl).val() + '&query=' + $(dom.searchControl).val();
    })
    .skipDuplicates()
    .doAction(showSpinner)
    .doAction(BU.recordUrl)
    .flatMap(function(url) {
        return Bacon.fromPromise($.ajax({
            url: url
        }));
    });

searchResponseStream.onValue($container, 'html');
searchResponseStream.onValue(hideSpinner);

BU.reloadContainerOnClickAndRecordUrl($container, dom.pagingControls, dom.sortingControls);

function getUpdatedUserRoles() {
    var updates = {
        users: {},
        invites: {}
    };

    function getData(row) {
        var data = {},
            $row = $(row);
        data[$row.data('user-id')] = {
            admin: $row.find('input[data-field$="-admin"]').is(":checked"),
            role: $row.find('select[data-field$="-role"]').val()
        };
        return data;
    }

    $(dom.invited).children().each(function (i, row) {
        $.extend(updates.invites, getData(row));
    });

    $(dom.users).children().each(function (i, row) {
        $.extend(updates.users, getData(row));
    });

    return updates;
}

$removeInviteModal.on('show.bs.modal', function(e) {
    var $row = $(e.relatedTarget).closest('[data-user-id]'),
        id = $row.attr('data-user-id');

    $removeInviteModal
        .data('id', id)
        .data('row', $row);
});

$(dom.removeInvite).on('click', function() {
    var id = $removeInviteModal.data('id'),
        $row = $removeInviteModal.data('row');

    $.ajax({
        'url': reverse.user_invite(config.instance.url_name, id),
        'method': 'DELETE',
    })
    .done(function() {
        $row.remove();
    })
    .fail(function() {
        toastr.error('Could not remove invitation');
    })
    .always(function() {
        $removeInviteModal.modal('hide');
    });
});
