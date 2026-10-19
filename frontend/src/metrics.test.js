import test from 'node:test';
import assert from 'node:assert/strict';
import {percent, metric, score} from './metrics.js';

test('percentages derive from observed counts, never demo capacity', () => {
  assert.equal(percent(10, 94), '10.6%');
  assert.equal(percent(10, 76), '13.2%');
  assert.equal(percent(76, 936), '8.1%');
  assert.equal(percent(0, 0), 'Not estimable');
});
test('unscored and non-probability metrics are not shown as zero', () => {
  assert.equal(score(null), 'Unscored');
  assert.equal(metric(null), 'Not applicable');
  assert.equal(score(10.2552814032756), '10.26');
});
