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
       marker-width: 20;
    }
    [zoom = 17] {
       marker-width: 15;
    }
    [zoom = 16] {
       marker-width: 12;
    }
    [zoom = 15] {
       marker-width: 8;
    }
    [zoom <= 14] {
       marker-width: 5;
    }

}
