module.exports = function(grunt) {
    "use strict";

    var debug = typeof grunt.option('dev') !== "undefined";

    grunt.loadNpmTasks('grunt-browserify');
    grunt.loadNpmTasks('grunt-contrib-jshint');
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-sass');
    grunt.loadNpmTasks('grunt-contrib-concat');
    grunt.loadNpmTasks('grunt-contrib-cssmin');
    grunt.file.setBase('opentreemap');

    grunt.registerTask('check', ['jshint']);
    grunt.registerTask('js', debug ? ['browserify'] : ['browserify', 'uglify']);
    grunt.registerTask('css', debug ? ['sass', 'concat'] : ['sass', 'concat', 'cssmin']);
    grunt.registerTask('default', ['js', 'css']);

    /*
     * Reads the extra.json file which should be a dictionary
     * where the keys are the require.js alias and the values
     * are the path to a file, relative to `opentreemap`
     */
    function getAliases() {
        var aliases = ['treemap/js/src/app.js:app',
                       'treemap/js/src/user.js:user',
                       'treemap/js/src/plot.js:plot',
                       'treemap/js/src/openLayersMapEventStream:' +
                       'openLayersMapEventStream'];

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
                    debug: debug
                }
            }
        },
        jshint: {
            options: {
                jshintrc: "../.jshintrc"
            },
            treemap: ['../Gruntfile.js', '*/js/src/**/*.js']
        },
        uglify: {
            options: {
                mangle: {
                    except: ['require', 'google']
                }
            },
            treemap: {
                files: {
                    'treemap/static/js/treemap.min.js': ['treemap/static/js/treemap.js']
                }
            }
        },
        sass: {
            treemap: {
                options: {
                    includePaths: ['treemap/css/sass/']
                },
                files: {
                    'treemap/static/css/main.css': 'treemap/css/sass/main.scss'
                }
            }
        },
        concat: {
            treemap: {
                src: ['treemap/css/vendor/*.css'],
                dest: 'treemap/static/css/vendor.css'
            }
        },
        cssmin: {
            treemap: {
                files: {
                    'treemap/static/css/vendor.min.css': ['treemap/static/css/vendor.css'],
                    'treemap/static/css/main.min.css': ['treemap/static/css/main.css']
                }
            }
        }
    });
};
