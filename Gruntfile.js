module.exports = function(grunt) {
    "use strict";

    grunt.loadNpmTasks('grunt-browserify');
    grunt.loadNpmTasks('grunt-contrib-jshint');
    grunt.file.setBase('opentreemap');
    grunt.registerTask('check', ['jshint']);
    grunt.registerTask('default', ['browserify']);


    /*
     * Reads the extra.json file which should be a dictionary
     * where the keys are the require.js alias and the values
     * are the path to a file, relative to `opentreemap`
     */
    function getAliases() {
        var aliases = ['treemap/js/src/app.js:app',
                       'treemap/js/src/user.js:user'];

        var extras = require('./extra.json');
        for (var alias in extras) {
            var filepath = extras[alias];
            if (grunt.file.exists(filepath)) {
                aliases.push(filepath + ':' + alias);
            }
        }
        return aliases;
    }

    grunt.initConfig({
        browserify: {
            treemap: {
                src: [],
                dest: 'treemap/static/js/treemap.js',
                options: {
                    alias: getAliases(),
                    aliasMappings: {
                        cwd:'treemap/js/lib/',
                        src: ['*.js'],
                        dest: '',
                        ext: '',
                        flatten: true
                    },
                    noParse: grunt.file.expand('*/js/lib/*.js'),
                    shim: {
                        OpenLayers: {
                            path: './treemap/js/shim/OpenLayers.js',
                            exports: 'OpenLayers',
                            depends: { googlemaps: 'google' }
                        },
                        // Typeahead puts itself onto the jQuery object
                        typeahead: {
                            path: './treemap/js/shim/typeahead.js',
                            exports: null,
                            depends: { jquery: 'jQuery' }
                        },
                        // Bootstrap puts itself onto the jQuery object
                        bootstrap: {
                            path: './treemap/js/shim/bootstrap.js',
                            exports: null,
                            depends: { jquery: 'jQuery' }
                        }
                    },
                    debug: true
                }
            }
        },
        jshint: {
            options: {
                jshintrc: "../.jshintrc"
            },
            treemap: ['../Gruntfile.js', '*/js/src/**/*.js']
        }
    });
};
