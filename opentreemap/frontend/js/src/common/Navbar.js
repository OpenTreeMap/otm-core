import React, { Component } from 'react';
import {Navbar, Nav} from 'react-bootstrap';
import {BrowserRouter as Router, Route, Switch} from 'react-router-dom';

import Users from './admin/Users';
import Admin from './admin/Admin';
import MapMain from './map/MapMain';
import Map from './map/Map';

import 'bootstrap/dist/css/bootstrap.min.css';


class App extends Component {
    constructor(props) {
        super(props);
        this.state = { };
    }

    render() {
        return (
            <div>
                <Navbar>
                    <Navbar.Collapse className="pull-left navbar-nav navbar-left">
                        <Nav>
                            <Nav.Link href="/">Add A Tree</Nav.Link>
                            <Nav.Link href="/map">Explore Map</Nav.Link>
                            <Nav.Link href="/users">View Edits</Nav.Link>
                            <Nav.Link href="/admin">Manage</Nav.Link>
                            <Nav.Link href="/users">Dashboard</Nav.Link>
                            <Nav.Link href="/users">Users</Nav.Link>
                        </Nav>
                    </Navbar.Collapse>

                    <Navbar.Collapse className="pull-right navbar-nav navbar-right">
                        <Nav>
                            <Nav.Link href="/users">Login</Nav.Link>
                        </Nav>
                    </Navbar.Collapse>
                </Navbar>
                <Router>
                    <Switch>
                        <Route path='/admin' component={Admin} />
                        <Route path='/map' component={MapMain} />
                        <Route exact path='/' component={Users} />
                    </Switch>
                </Router>
            </div>
        );
    }
}



export default App;
