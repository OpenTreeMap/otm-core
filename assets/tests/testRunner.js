"use strict";
// Reference: http://kirbysayshi.com/2013/07/01/mocha-tests-node-and-browser.html

// This code is adapted from mocha/lib/interfaces/exports.js

// This should allow us to require any test file
var req = require.context('../../opentreemap', true, /js\/test\/.*\.js/);
var testModules = req.keys();

testModules.forEach(function(moduleName) {
    var testModule = req(moduleName);
    var suites = [window.mocha.suite];

    visit(testModule);

    function visit(obj) {
        for (var key in obj) {
            if ('function' == typeof obj[key]) {
                var fn = obj[key];
                switch (key) {
                case 'before':
                    suites[0].beforeAll(fn);
                    break;
                case 'after':
                    suites[0].afterAll(fn);
                    break;
                case 'beforeEach':
                    suites[0].beforeEach(fn);
                    break;
                case 'afterEach':
                    suites[0].afterEach(fn);
                    break;
                default:
                    suites[0].addTest(new window.Mocha.Test(key, fn));
                }
            } else {
                var suite = window.Mocha.Suite.create(suites[0], key);
                suites.unshift(suite);
                visit(obj[key]);
                suites.shift();
            }
        }
    }
});
