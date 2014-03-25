"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    U = require('treemap/utility');

module.exports = {
    init: function ($container) {
        var $steps = U.$find('.add-step', $container),
            maxStepNumber = $steps.length - 1,
            $nextButtons = U.$find('.next', $steps),
            $prevButtons = U.$find('.previous', $steps),
            stepChangeStartStream = Bacon.mergeAll(
                $nextButtons.asEventStream('click')
                    .filter(isEnabled)
                    .map(function (e) {
                        return getStepNumber(e.target) + 1;
                    }),
                $prevButtons.asEventStream('click')
                    .filter(isEnabled)
                    .map(function (e) {
                        return getStepNumber(e.target) - 1;
                    })
            ),
            stepChangeCompleteStream = $steps.asEventStream('transitionend webkitTransitionEnd')
                .filter(function (e) {
                    return $(e.target).hasClass('active');
                })
                .map(function (e) {
                    return $(e.target).index();
                });

        stepChangeStartStream.onValue(showStep);

        function isEnabled(e) {
            return !$(e.target).closest('li').hasClass('disabled');
        }

        function getStepNumber(button) {
            return $(button).closest('.add-step').index();
        }

        function showStep(stepNumber) {
            if (stepNumber <= maxStepNumber) {
                $steps.removeClass('active next prev');
                $steps.eq(stepNumber).addClass('active');
                for (var i = 0; i < stepNumber; i++) {
                    $steps.eq(i).addClass('prev');
                }
                for (var i = maxStepNumber; i > stepNumber; i--) {
                    $steps.eq(i).addClass('next');
                }
            }
        }

        function enableNext(stepNumber, shouldEnable) {
            var $next = $nextButtons.eq(stepNumber);
            if (shouldEnable) {
                $next.removeClass('disabled');
            } else {
                $next.addClass('disabled');
            }
        }

        return {
            maxStepNumber: maxStepNumber,
            stepChangeStartStream: stepChangeStartStream,
            stepChangeCompleteStream: stepChangeCompleteStream,
            allDoneStream: $nextButtons.last().asEventStream('click'),
            showStep: showStep,
            enableNext: enableNext
        };
    }
};
