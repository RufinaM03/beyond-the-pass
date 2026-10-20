export function manualPayload(fields, eligible) {
  if (!eligible) throw new Error('Confirm the intended inspection scope before requesting a score.');
  const optionalNumber = key => fields[key].trim() === '' ? null : Number(fields[key]);
  const features = {
    vehicle_age_years: optionalNumber('vehicle_age_years'),
    mileage: optionalNumber('mileage'),
    brake_advisory_count: fields.brake_advisory_count.trim() === '' ? NaN : Number(fields.brake_advisory_count),
    advisory_count: fields.advisory_count.trim() === '' ? NaN : Number(fields.advisory_count),
  };
  if (features.vehicle_age_years !== null && (!Number.isFinite(features.vehicle_age_years) || features.vehicle_age_years < 0 || features.vehicle_age_years > 1000)) throw new Error('Age must be 0–1,000 years or left blank. This is a technical limit, not a validity guarantee.');
  if (features.mileage !== null && (!Number.isFinite(features.mileage) || features.mileage <= 0 || features.mileage > 1e9)) throw new Error('Mileage must be positive miles, at most 1,000,000,000, or left blank.');
  for (const key of ['brake_advisory_count', 'advisory_count']) {
    if (!Number.isInteger(features[key]) || features[key] < 1 || features[key] > 10000) throw new Error('Both advisory counts must be known whole numbers from 1 to 10,000.');
  }
  if (features.advisory_count < features.brake_advisory_count) throw new Error('Total advisories must include all brake advisories.');
  return {eligibility_confirmed: true, features, inspection_date: fields.inspection_date || null};
}

export const manualNames = {
  vehicle_age_years: 'Vehicle age (years)', mileage: 'Recorded mileage (miles)',
  brake_advisory_count: 'Current brake advisories', advisory_count: 'Total current advisories',
  missingindicator_vehicle_age_years: 'Missing age indicator', missingindicator_mileage: 'Missing mileage indicator',
};

export function strongestTerms(prediction) {
  return [...(prediction.explanation?.terms || [])].filter(term => term.log_odds_contribution !== 0)
    .sort((first, second) => Math.abs(second.log_odds_contribution) - Math.abs(first.log_odds_contribution) || first.feature.localeCompare(second.feature)).slice(0, 3);
}
