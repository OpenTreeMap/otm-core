"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),
    BU = require('treemap/lib/baconUtils.js');

require('bootstrap');

var dom = {
    nav: '#tab-list',
    toggleSidebar: '#toggle-sidebar',
    management: '#management',
    notifications: '[data-admin-notification]',
};

module.exports.init = function (updateStream) {
    // Add bacon to jquery
    $.extend($.fn, Bacon.$);

    var csrf = require('treemap/lib/csrf.js');
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    function toggleIcon(oldIcon, newIcon, section) {
        var $section = $(section),
            $link = $(dom.nav).find('[data-toggle="collapse"][data-target="#' + $section.attr('id') + '"]');
        $link.find('.' + oldIcon)
            .removeClass(oldIcon)
            .addClass(newIcon);
    }

    $(dom.nav).asEventStream('show.bs.collapse')
        .map('.target')
        .onValue(toggleIcon, 'icon-left-open', 'icon-down-open');
    $(dom.nav).asEventStream('hide.bs.collapse')
        .map('.target')
        .onValue(toggleIcon, 'icon-down-open', 'icon-left-open');

    $(dom.toggleSidebar).on('click', function() {
        $(dom.management).toggleClass('slim');
    });

    var updateCountStream = Bacon.once(undefined);
    if (updateStream) {
        updateCountStream = Bacon.mergeAll(updateCountStream, updateStream.map(undefined));
    }

    updateCountStream
        .flatMap(BU.jsonRequest('GET', $(dom.management).data('update-url')))
        .onValue(function(notifications) {
            $(dom.notifications).each(function(i, elem) {
                var $elem = $(elem),
                    name = $elem.attr('data-admin-notification'),
                    count = notifications.admin_notifications[name];
                $elem.html(count);
            });
        });

    $(window).on('beforeunload', function() {
        if ($('.editBtn').is(':hidden')) {
            return 'Are you sure you want to leave?';
        }
    });
};
