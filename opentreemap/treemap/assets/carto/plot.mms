#treemap_plot {
    marker-fill: #8BAA3D;
    marker-allow-overlap: true;
    marker-line-width: 1;

    
    [zoom >= 15] {
        marker-line-color: #b6ce78;    
    }
    [zoom < 15] {
        marker-line-color: #8BAA3D;
    }


    [zoom >= 18] {
       marker-width: 10;
    }
    [zoom >= 17][zoom < 18] {
       marker-width: 9;
    }
    [zoom >= 16][zoom < 17] {
       marker-width: 8;
    }
    [zoom >= 15][zoom < 16] {
       marker-width: 7;
    }
    [zoom >= 14][zoom < 15] {
       marker-width: 6;
    }
    [zoom >= 13][zoom < 14] {
       marker-width: 5;
    }
    [zoom >= 12][zoom < 13] {
       marker-width: 4;
    }
    [zoom < 12] {
       marker-width: 3;
    }

}
