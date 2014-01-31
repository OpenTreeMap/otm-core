#treemap_boundary {
	::case {
    	line-width: 5;
    	line-color:#ddd;
    	line-opacity: 0.4;
  	}
  	::fill {
    	line-width: 0.5;
    	line-color: #444;
    	line-dasharray: 10, 8;
  	}

    [zoom < 16] {
        ::case {
    	    line-width: 0;    
        }
        ::fill {
            line-width: 0;  
        }
    }
}
