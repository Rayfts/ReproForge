import React from 'react';

export function Greeting({ name }) {
  return React.createElement('strong', null, `Hello ${name.toUpperCase()}`);
}
