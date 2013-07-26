module.exports = function(grunt) {
    "use strict";

    grunt.initConfig({
        browserify: {
            treemap: {
                src: [],
                dest: 'static/js/treemap.js',
                options: {
                    alias: ['js/src/app.js:treemap'],
                    aliasMappings: {
                        cwd: 'js/lib/',
                        src: ['*.js'],
                        dest: '',
                        ext: '',
                        flatten: true
                    },
                    shim: {
                        googlemaps: {
                            path: './js/shim/googlemaps.js',
                            exports: 'google'
                        },
                        OpenLayers: {
                            path: './js/shim/OpenLayers.js',
                            exports: 'OpenLayers',
                            depends: { googlemaps: 'google' }
                        }
                    },
                    debug: true
                }
            }
        },
        jshint: {
            options: {
                indent: 4,
                globalstrict: true, // Node.js modules are inherently wrapped in functions
                browser: true,
                globals: {
                    require: false,
                    module: true,
                    exports: true
                }
            },
            treemap: ['../../Gruntfile.js', 'js/src/**/*.js']
        }
    });

    grunt.loadNpmTasks('grunt-browserify');
    grunt.loadNpmTasks('grunt-contrib-jshint');

    grunt.file.setBase('opentreemap', 'treemap');
    grunt.registerTask('default', ['browserify']);
    grunt.registerTask('check', ['jshint']);
};
