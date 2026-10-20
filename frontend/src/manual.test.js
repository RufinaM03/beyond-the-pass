import test from 'node:test';
import assert from 'node:assert/strict';
import {manualPayload, strongestTerms} from './manual.js';

const illustrative = {vehicle_age_years: '10', mileage: '80000', brake_advisory_count: '1', advisory_count: '2', inspection_date: ''};
test('manual blanks stay null, not zero; known counts and eligibility are mandatory', () => {
  const payload = manualPayload({...illustrative, vehicle_age_years: ' ', mileage: ''}, true);
  assert.equal(payload.features.vehicle_age_years, null);
  assert.equal(payload.features.mileage, null);
  assert.throws(() => manualPayload(illustrative, false));
  for (const changed of [{advisory_count: ''}, {brake_advisory_count: '1.5'}, {mileage: 'Infinity'}, {mileage: '-2'}, {mileage: '0'}, {advisory_count: '1', brake_advisory_count: '2'}]) assert.throws(() => manualPayload({...illustrative, ...changed}, true));
});
test('date stays context and signed terms come from actual contributions, not fabricated importance', () => {
  const payload = manualPayload({...illustrative, inspection_date: '2024-02-29'}, true);
  assert.equal(payload.inspection_date, '2024-02-29');
  assert.deepEqual(Object.keys(payload.features), ['vehicle_age_years', 'mileage', 'brake_advisory_count', 'advisory_count']);
  const terms = [{feature: 'mileage', log_odds_contribution: -.2}, {feature: 'vehicle_age_years', log_odds_contribution: .3}];
  assert.equal(strongestTerms({explanation: {terms}})[0], terms[1]);
  assert.equal(terms[0].feature, 'mileage');
});
