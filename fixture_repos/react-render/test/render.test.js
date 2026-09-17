import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { Greeting } from '../src/Greeting.js';

test('preserves the supplied display name', () => {
  const html = renderToStaticMarkup(React.createElement(Greeting, { name: 'Ray' }));
  assert.equal(html, '<strong>Hello Ray</strong>');
});
