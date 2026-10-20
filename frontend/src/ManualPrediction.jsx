import React, {useEffect, useRef, useState} from 'react';
import {score} from './metrics.js';
import {manualNames, manualPayload, strongestTerms} from './manual.js';

const empty = {vehicle_age_years: '', mileage: '', brake_advisory_count: '', advisory_count: '', inspection_date: ''};

export default function ManualPrediction() {
  const [fields, setFields] = useState(empty);
  const [eligible, setEligible] = useState(false);
  const [info, setInfo] = useState(null);
  const [metadataAttempt, setMetadataAttempt] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const controller = useRef(null);
  useEffect(() => {
    const metadata = new AbortController();
    fetch('/api/prediction-info', {signal: metadata.signal}).then(response => {
      if (!response.ok) throw new Error('Verified prediction metadata is unavailable.');
      return response.json();
    }).then(setInfo).catch(failure => {if (failure.name !== 'AbortError') setError(failure.message);});
    return () => {metadata.abort(); controller.current?.abort();};
  }, [metadataAttempt]);
  function update(key, value) {setFields(current => ({...current, [key]: value})); setResult(null); setError('');}
  async function submit(event) {
    event.preventDefault();
    setError(''); setResult(null);
    let payload;
    try {payload = manualPayload(fields, eligible);} catch (failure) {setError(failure.message); return;}
    controller.current?.abort();
    controller.current = new AbortController();
    setPending(true);
    try {
      const response = await fetch('/api/predict/manual', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload), signal: controller.current.signal});
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : (body.detail || []).map(item => item.msg).join('; ') || 'Prediction unavailable.');
      setResult(body);
    } catch (failure) {if (failure.name !== 'AbortError') setError(failure.message);}
    finally {setPending(false);}
  }
  const prediction = result?.prediction;
  return <>
    <header className="page-heading"><p className="eyebrow">02 / Manual scenario</p><h1>Try a prediction</h1><div className="lede"><p>Enter conditions at one inspection, not a vehicle identity. This is a new illustrative scenario, not a historical record or observed outcome.</p></div></header>
    <aside className="notice">This exploratory model concerns recorded brake failure at the immediate next qualifying normal inspection, 9–15 calendar months later. It does not predict accidents, breakdowns, present roadworthiness or a specific failure date.</aside>
    <section className="panel"><h2>Inspection conditions</h2><p>No registration, VIN, name or personal information is needed. Submissions are not stored or added to the historical queue. Only the four supported predictors are used; no recurrence or time-since-advisory input.</p>
      {!info && !error && <p role="status">Loading verified model metadata…</p>}
      <form onSubmit={submit} className="manual-form">
        <fieldset disabled={pending}><legend>Eligibility confirmation</legend><label className="confirmation"><input type="checkbox" checked={eligible} onChange={event => {setEligible(event.target.checked); setResult(null);}}/>I confirm this is a Class 4, passed normal inspection (NT / P), with at least one current brake advisory.</label><p className="footnote">Other components, retests, failed starting inspections and rectification-at-station (PRS) starts are outside this model’s intended scope.</p></fieldset>
        <fieldset disabled={pending}><legend>Predictors available at the inspection</legend><div className="manual-fields">
          <label htmlFor="manual-age">Vehicle age in years<input id="manual-age" type="number" min="0" max="1000" step="any" value={fields.vehicle_age_years} onChange={event => update('vehicle_age_years', event.target.value)} aria-describedby="age-help"/><small id="age-help">At this inspection, not today. Leave blank if unknown.</small></label>
          <label htmlFor="manual-mileage">Recorded mileage (miles)<input id="manual-mileage" type="number" min="0.000001" max="1000000000" step="any" value={fields.mileage} onChange={event => update('mileage', event.target.value)} aria-describedby="mileage-help"/><small id="mileage-help">Enter positive miles, not kilometres. Leave blank if unavailable; zero is not an unknown-value substitute.</small></label>
          <label htmlFor="manual-brakes">Current brake advisory count<input id="manual-brakes" type="number" required min="1" max="10000" step="1" value={fields.brake_advisory_count} onChange={event => update('brake_advisory_count', event.target.value)} aria-describedby="count-help"/></label>
          <label htmlFor="manual-total">Total current advisory count<input id="manual-total" type="number" required min="1" max="10000" step="1" value={fields.advisory_count} onChange={event => update('advisory_count', event.target.value)} aria-describedby="count-help"/></label>
        </div><p id="count-help" className="footnote">Total includes brake advisories and must be at least the brake count. Count advisory (A) items, not minor (M) defects. Counts must be known; blanks are never silently zero. Numeric maxima are technical request limits, not plausible-vehicle or reliability thresholds.</p></fieldset>
        {info && <p className="footnote">{info.mileage_note} If age or mileage is blank, the frozen training median and learned missingness indicator are used. Both blank gives insufficient data, not a score.</p>}
        <label htmlFor="manual-date">Inspection date (optional context)<input id="manual-date" type="date" min="1900-01-01" max="2100-12-31" value={fields.inspection_date} disabled={pending} onChange={event => update('inspection_date', event.target.value)} aria-describedby="date-help"/></label><small id="date-help">The date is not a predictor. It only displays the nominal 9–15-calendar-month cohort observation window, not time to failure.</small>
        <div className="actions"><button disabled={!eligible || !info || pending}>{pending ? 'Calculating…' : 'Calculate exploratory score'}</button><button type="button" className="secondary" disabled={pending} onClick={() => {setFields({...empty, vehicle_age_years: '10', mileage: '80000', brake_advisory_count: '1', advisory_count: '2'}); setEligible(false); setResult(null); setError('');}}>Load illustrative inputs</button></div><p className="footnote">Illustrative inputs are invented values for exploring the form, not a real historical inspection. They still require your scope confirmation.</p>
      </form>
    </section>
    {error && <section className="panel state" role="alert"><h2>Prediction unavailable</h2><p>{error}</p><p>Check the inputs or retry. No substitute score is shown.</p>{!info && <button onClick={() => {setError(''); setMetadataAttempt(value => value + 1);}}>Retry model metadata</button>}</section>}
    {pending && <p role="status">Using the verified model and its original preprocessing…</p>}
    {prediction && <section className="panel manual-result" aria-live="polite"><p className="eyebrow">Your submitted scenario · not observed data</p><h2>{prediction.status === 'scored' ? 'Exploratory prioritization score' : 'Insufficient data — no score'}</h2>
      <div className="manual-score">{score(prediction.exploratory_prioritization_score)}{prediction.status === 'scored' && <small> / 100</small>}</div>
      <aside className="notice">Not a calibrated failure percentage, diagnosis, safety assessment or inspection substitute. This scenario receives no historical rank or percentile. The saved 936-example evaluation is unchanged.</aside>
      <h3>Submitted conditions</h3><dl className="feature-grid">{Object.entries(result.submitted_features).map(([key, value]) => <div key={key}><dt>{manualNames[key]}</dt><dd>{value === null ? 'Unknown (submitted blank)' : value.toLocaleString()}</dd></div>)}</dl>
      {prediction.status !== 'scored' ? <p>{prediction.reasons?.join('. ')}. Provide at least age or positive mileage.</p> : <>
        <p><strong>Imputed inputs:</strong> {Object.keys(result.imputed_values).length ? Object.entries(result.imputed_values).map(([key, value]) => `${manualNames[key]}: frozen median ${value.toLocaleString()}`).join('; ') : 'None'}. Imputation does not make missing information observed.</p>
        <h3>What moves this model’s score?</h3><p>The largest absolute signed terms for this submission are listed below. They compare transformed inputs with training-centered values; they are mathematical associations, not repair advice or causal diagnoses.</p><ul>{strongestTerms(prediction).map(term => <li key={term.feature}><strong>{manualNames[term.feature] || term.feature}</strong> pushes the model’s score {term.log_odds_contribution > 0 ? 'upward' : 'downward'} relative to the centered-input reference.</li>)}</ul>
        <details><summary>Technical explanation: all model contributions</summary><div className="table-scroll"><table><caption>Log-odds contributions, not percentage points; all terms included</caption><thead><tr><th scope="col">Term</th><th scope="col">Signed contribution</th></tr></thead><tbody><tr><td>Intercept</td><td>{prediction.explanation.intercept_log_odds.toFixed(6)}</td></tr>{prediction.explanation.terms.map(term => <tr key={term.feature}><td>{manualNames[term.feature] || term.feature}</td><td>{term.log_odds_contribution.toFixed(6)}</td></tr>)}</tbody></table></div><p>100 × sigmoid(intercept + sum of all terms) = score. Displayed values are rounded; the API preserves full precision. Recurrence is not used.</p></details>
        <aside className="notice"><strong>{prediction.outside_training_range.length ? 'Extrapolation warning' : 'Range check is not a reliability guarantee'}</strong><p>{prediction.outside_training_range.length ? `Outside observed training ranges: ${prediction.outside_training_range.map(key => manualNames[key] || key).join(', ')}.` : 'None of the provided inputs is outside its observed training range.'} In-range inputs do not establish reliability; calibration, transportability and recurrence’s predictive value remain unvalidated.</p></aside>
      </>}
      <h3>Inspection-date context</h3><p>{result.inspection_date || 'No inspection date supplied.'} {result.nominal_followup_window && `Nominal window: ${result.nominal_followup_window.start} to ${result.nominal_followup_window.end}, inclusive.`} {result.context_note}</p>
      <p className="footnote">Model {prediction.model_version} · Data {prediction.data_version} · No submission stored. No observed outcome is created.</p>
    </section>}
  </>;
}
