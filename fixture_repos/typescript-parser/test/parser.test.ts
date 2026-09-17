import assert from 'node:assert/strict';
import test from 'node:test';
import { parsePair } from '../src/parser.ts';

test('keeps colons inside the value', () => {
  assert.deepEqual(parsePair('url:https://example.test'), {
    key: 'url',
    value: 'https://example.test',
  });
});
