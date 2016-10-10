"use strict";

/*
 Sticky Headers

 In a scrolling list of sections, ensure that header of first visible section
 is always visible. Works with add/remove section and collapse/expand section.

 Adds either "fixed" or "absolute" class to a header when its section is
 the first visible.

 CSS class "fixed" should use position:fixed so the header won't scroll.

 Class "absolute" is used when the header is at the bottom of its section.
 CSS should use position:absolute so the header will scroll off the top.

 The header must be wrapped by a <div>, used to preserve its height when
 its positioning changes.
 */


var $ = require('jquery');

module.exports = function ($scrollContainer, stickiesSelector, $positionContainer) {

    var self = {};

    $scrollContainer.off("scroll").on("scroll", function() {
        self.update();
    });

    self.update = function() {

        var $stickies = $(stickiesSelector);

        for (var i = $stickies.length - 1; i >= 0; --i) {

            var $sticky = $stickies.eq(i);

            if (getTop($sticky) < 0) {
                // Found sticky of first visible section
                if (i === $stickies.length - 1) {
                    // Final section always uses "fixed"
                    updateActiveSticky($sticky, 'fixed');
                } else {
                    var bottom = getTop($stickies.eq(i + 1)),
                        height = $sticky.outerHeight();
                    if (height < bottom) {
                        updateActiveSticky($sticky, 'fixed');
                    } else {
                        updateActiveSticky($sticky, 'absolute');
                        $sticky.css("top", $scrollContainer.scrollTop() + bottom - height);
                    }
                }
                return;
            }
        }
        clearOverrides($stickies);

        function updateActiveSticky($sticky, cssClass) {
            if (!$sticky.hasClass(cssClass)) {
                $sticky.parent().height($sticky.outerHeight());  // parent preserves vertical space
                clearOverrides($stickies);
                $sticky.addClass(cssClass);
            }
        }
    };

    function getTop($sticky) {
        var containerOffset = $scrollContainer.offset(),
            containerTop = containerOffset ? containerOffset.top
                : $scrollContainer.scrollTop() + $positionContainer.offset().top,
            top = $sticky.parent().offset().top - containerTop;
        return top;
    }

    function clearOverrides($stickies) {
        $stickies
            .removeClass('fixed')
            .removeClass('absolute')
            .css('top', '');
    }

    return self;
};
