import {createPublicKey, verify} from 'node:crypto';
import {pathToFileURL} from 'node:url';

const issuer = 'https://token.actions.githubusercontent.com';
const subject = 'repo:RufinaM03@162699034/beyond-the-pass@1425804589:ref:refs/heads/main';
const role = 'arn:aws:iam::044854093109:role/BtpProductionImageDeployment';

export function inspectToken(token, keys, now = Math.floor(Date.now() / 1000)) {
  if (typeof token !== 'string' || token.length > 32768) throw new Error('Invalid token structure');
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Invalid token structure');
  const header = JSON.parse(Buffer.from(parts[0], 'base64url').toString());
  const claims = JSON.parse(Buffer.from(parts[1], 'base64url').toString());
  const key = keys.find(entry => entry.kid === header.kid && entry.kty === 'RSA');
  const signatureValid = Boolean(header.alg === 'RS256' && key && verify('RSA-SHA256', Buffer.from(parts[0] + '.' + parts[1]),
    createPublicKey({key, format: 'jwk'}), Buffer.from(parts[2], 'base64url')));
  return {
    issuer_matches: claims.iss === issuer,
    audience_matches: claims.aud === 'sts.amazonaws.com',
    immutable_main_subject_matches: claims.sub === subject,
    public_signing_key_found: Boolean(key),
    signature_valid: signatureValid,
    time_valid: Number.isFinite(claims.iat) && Number.isFinite(claims.exp) && claims.iat <= now + 30 && claims.exp > now,
    issued_seconds_ago: Number.isFinite(claims.iat) ? now - claims.iat : null,
    expires_in_seconds: Number.isFinite(claims.exp) ? claims.exp - now : null,
  };
}

async function probe(endpoint, token) {
  const response = await fetch(endpoint, {method: 'POST', signal: AbortSignal.timeout(20000),
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({Action: 'AssumeRoleWithWebIdentity', Version: '2011-06-15', RoleArn: role,
      RoleSessionName: 'btp-oidc-diagnostic', DurationSeconds: '900', WebIdentityToken: token})});
  if (response.ok) {
    await response.body?.cancel();
    return {http_status: response.status, code: 'Success'};
  }
  const body = await response.text();
  return {http_status: response.status, code: body.match(/<Code>([A-Za-z0-9]+)<\/Code>/)?.[1] || 'UnclassifiedError'};
}

export async function main() {
  const report = {diagnostic_only: true, aws_resource_mutations: false};
  try {
    const tokenUrl = new URL(process.env.ACTIONS_ID_TOKEN_REQUEST_URL);
    tokenUrl.searchParams.set('audience', 'sts.amazonaws.com');
    const response = await fetch(tokenUrl, {headers: {Authorization: 'Bearer ' + process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN}, signal: AbortSignal.timeout(20000)});
    if (!response.ok) throw new Error('Token request failed');
    const token = (await response.json()).value;
    const discovery = await (await fetch(issuer + '/.well-known/openid-configuration', {signal: AbortSignal.timeout(20000)})).json();
    if (discovery.issuer !== issuer || !discovery.jwks_uri.startsWith(issuer + '/')) throw new Error('Unexpected issuer discovery');
    const keys = (await (await fetch(discovery.jwks_uri, {signal: AbortSignal.timeout(20000)})).json()).keys;
    report.claim_checks = inspectToken(token, keys);
    report.public_key_count = keys.length;
    const checks = report.claim_checks;
    if (![checks.issuer_matches, checks.audience_matches, checks.immutable_main_subject_matches,
      checks.public_signing_key_found, checks.signature_valid, checks.time_valid].every(Boolean)) {
      report.result = 'TokenContractMismatch';
    } else {
      report.regional_sts = await probe('https://sts.ap-south-1.amazonaws.com/', token);
      if (report.regional_sts.code === 'InvalidIdentityToken') report.global_sts = await probe('https://sts.amazonaws.com/', token);
      report.result = report.regional_sts.code;
    }
  } catch {
    report.result = 'DiagnosticRequestFailed';
  }
  console.log(JSON.stringify(report, null, 2));
  if (report.result !== 'Success') process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
