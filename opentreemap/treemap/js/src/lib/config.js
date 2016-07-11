"use strict";

// window.otm is expected to be undefined in our JS test runner
module.exports = window.otm && window.otm.settings ? Object.freeze(window.otm.settings) : {};
