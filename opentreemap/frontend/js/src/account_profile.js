import React from 'react';
import ReactDOM from 'react-dom';
import Profile from './account/Profile';

console.log('TEST');

ReactDOM.render(
  <React.StrictMode>
    <Profile />
  </React.StrictMode>,
  document.getElementById('app')
);
