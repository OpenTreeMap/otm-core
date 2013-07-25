module.exports = function(grunt) {
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
        }
    });

    grunt.loadNpmTasks('grunt-browserify');

    grunt.file.setBase('opentreemap', 'treemap');
    grunt.registerTask('bundle', ['browserify']);
};
