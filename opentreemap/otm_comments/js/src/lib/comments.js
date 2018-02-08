"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    csrf = require('treemap/lib/csrf.js'),
    config = require('treemap/lib/config.js'),
    flagging = require('otm_comments/lib/flagging.js');

var TEMPLATE_SELECTOR = "#template-comment",
    COMMENT_ID_ATTR = "data-comment-id";

module.exports = function(commentContainerSelector) {
    var $container = $(commentContainerSelector);

    // Set up cross-site forgery protection
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    function makeForm(data) {
        // We need to reload the comment form every time we use it, because it
        // contains security values that change whenever a comment is posted
        return _.template($(TEMPLATE_SELECTOR).html())(data);
    }

    function addMainForm() {
        if (config.loggedIn) {
            $container.append(makeForm({
                parent: '',
                classname: 'comment-create-form'
            }));
        }
    }

    $container.on('click', 'a[data-comment-id]', function (e) {
        e.preventDefault();

        var $link = $(e.target);

        // Close other forms
        $(".comment-reply-form").remove();

        $link.closest('.comment').append(makeForm({
            parent: $link.attr(COMMENT_ID_ATTR),
            classname: 'comment-reply-form'
        }));

        $('#id_comment').trigger('focus');
    });

    $container.on('change keyup paste', 'textarea', function (e) {
        var $textarea = $(e.currentTarget),
            $form = $textarea.closest('form'),
            $submit = $form.find('input[type="submit"]');

        if ($textarea.val().trim() === "") {
            $submit.prop('disabled', true);
        } else {
            $submit.prop('disabled', false);
        }
    });

    // The default comment form is not part of the page by default
    addMainForm();
    flagging();

    // Instead of a normal POST, we do a POST but then take the comment container
    // contents out of the results and stuff them into the comments container
    // on the page
    $container.on('click', '[type="submit"]', function(e) {
        e.preventDefault();
        var $postButton = $(e.target),
            $form = $postButton.closest('form'),
            // "URL"s with a selector in them tell $.load to only load that
            // part of the result into the element
            url = $form.attr('action') + " " + commentContainerSelector,
            paramsArray = $form.serializeArray(),
            params = {};

        _.each(paramsArray, function(paramObj) {
            params[paramObj.name] = paramObj.value;
        });

        $container.load(url, params, addMainForm);
    });
};
