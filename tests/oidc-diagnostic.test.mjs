import {test} from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPairSync, sign} from 'node:crypto';
import {inspectToken} from '../scripts/oidc-diagnostic.mjs';

const {privateKey, publicKey} = generateKeyPairSync('rsa', {modulusLength: 2048});
const key = {...publicKey.export({format: 'jwk'}), kid: 'synthetic-test-only'};
const claims = {iss: 'https://token.actions.githubusercontent.com', aud: 'sts.amazonaws.com',
  sub: 'repo:RufinaM03@162699034/beyond-the-pass@1425804589:ref:refs/heads/main', iat: 1000, exp: 1300};
const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url');
function fixture(values) {
  const unsigned = encode({alg: 'RS256', kid: key.kid}) + '.' + encode(values);
  return unsigned + '.' + sign('RSA-SHA256', Buffer.from(unsigned), privateKey).toString('base64url');
}

test('Synthetic signed JWT: checks only metadata, never returns token or credentials', () => {
  const token = fixture(claims);
  const report = inspectToken(token, [key], 1100);
  assert.equal(report.signature_valid, true);
  assert.equal(report.immutable_main_subject_matches, true);
  assert.equal(report.time_valid, true);
  assert.equal(JSON.stringify(report).includes(token), false);
  assert.equal('sub' in report, false);
});

test('Synthetic legacy subject, expiry and tampered signature are rejected', () => {
  assert.equal(inspectToken(fixture({...claims, sub: 'legacy-subject'}), [key], 1100).immutable_main_subject_matches, false);
  assert.equal(inspectToken(fixture(claims), [key], 1400).time_valid, false);
  const parts = fixture(claims).split('.');
  parts[1] = encode({...claims, aud: 'tampered'});
  const report = inspectToken(parts.join('.'), [key], 1100);
  assert.equal(report.signature_valid, false);
  assert.equal(report.audience_matches, false);
});
