export const percent = (numerator, denominator) => denominator > 0 ? `${(100 * numerator / denominator).toFixed(1)}%` : 'Not estimable';
export const metric = value => Number.isFinite(value) ? value.toFixed(4) : 'Not applicable';
export const score = value => Number.isFinite(value) ? value.toFixed(2) : 'Unscored';
export const names = {
  training_prevalence: 'Constant training prevalence',
  brakes_advisory_count: 'Current brakes advisory count',
  logistic: 'Fixed logistic model',
  vehicle_age_years: 'Vehicle age at index (years)',
  mileage: 'Recorded mileage at index',
  brake_advisory_count: 'Current brakes advisories',
  advisory_count: 'Current advisories · all families',
  missingindicator_mileage: 'Missing mileage indicator',
};
