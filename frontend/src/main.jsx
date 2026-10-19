import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {percent, metric, score, names} from './metrics.js';
import './style.css';

function useData(url) {
  const [state, setState] = useState({loading: true});
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({loading: true});
    fetch(url, {signal: controller.signal}).then(async response => {
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`);
      }
      return response.json();
    }).then(data => setState({data})).catch(error => {
      if (error.name !== 'AbortError') setState({error: error.message});
    });
    return () => controller.abort();
  }, [url, attempt]);
  return {...state, retry: () => setAttempt(value => value + 1)};
}

function Status({state, children}) {
  if (state.loading) return <div className="panel state" role="status">Loading verified release data…</div>;
  if (state.error) return <div className="panel state" role="alert"><h2>Data unavailable</h2><p>{state.error}</p><p>No substitute scores or metrics are shown.</p><button onClick={state.retry}>Try again</button></div>;
  return <>{state.data.fixture && <Warning><strong>SYNTHETIC CI FIXTURE — NOT A REAL RELEASE.</strong> All fixture rows, scores and metrics are invented software-test artifacts, not evidence of model performance. The real portfolio’s 200/936 population labels do not describe this fixture.</Warning>}{children(state.data)}</>;
}

function Link({to, children, className = '', ...props}) {
  return <a href={to} className={className} {...props} onClick={event => {
    if (!event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0) {
      event.preventDefault();
      history.pushState({}, '', to);
      window.dispatchEvent(new PopStateEvent('popstate'));
      window.scrollTo(0, 0);
    }
  }}>{children}</a>;
}

function Heading({eyebrow, title, children}) {
  return <header className="page-heading"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><div className="lede">{children}</div></header>;
}
function Stat({value, label, children}) {
  return <article className="panel stat"><span className="stat-value">{value}</span><h3>{label}</h3><p>{children}</p></article>;
}
function Warning({children}) {return <aside className="notice">{children}</aside>;}

function Overview({versions, evaluation}) {
  return <>
    <Heading eyebrow="The question beyond a pass" title="A pass isn’t the end of the story."><p>Which passed inspections with brake advisories should be prioritized for a follow-up check?</p></Heading>
    <section className="hero"><div><span className="tag">RETROSPECTIVE RESEARCH · CLASS 4 · BRAKES</span><h2>Turn recorded advisories into a focused follow-up list.</h2><p>An exploratory decision-support portfolio for fleet maintenance planners and inspection researchers. Review a historical demonstration, then examine the evidence behind it.</p><div className="actions"><Link className="button light" to="/queue">Explore the follow-up queue <span aria-hidden="true">↗</span></Link><Link className="quiet" to="/evaluation">Read the evaluation →</Link></div></div><div className="hero-mark" aria-hidden="true"><div className="disc"><span>BEYOND<br/>THE PASS</span></div></div></section>
    <Status state={evaluation}>{data => {
      const observed = data.primary_temporal.logistic;
      return <div className="stats"><Stat value={versions.demo_cases} label="Historical demo cases">A bounded, outcome-independent snapshot. Not a live fleet queue.</Stat><Stat value={observed.examples} label="Held-out evaluation examples">The full saved chronological evaluation, separate from the demo.</Stat><Stat value={`${observed.positive} / ${observed.examples}`} label="Recorded brake failures">{percent(observed.positive, observed.examples)} observed prevalence at the next qualifying inspection.</Stat></div>;
    }}</Status>
    <div className="two-col"><section className="panel"><p className="eyebrow">A narrow, explicit target</p><h2>Recorded failure at the next routine test</h2><p>Strict passed normal inspections with a brake advisory, followed by the immediate next normal inspection within 9–15 calendar months. Retests are not routine follow-ups.</p><p>Missing follow-up and out-of-window inspections are censored or excluded, not treated as negatives.</p><Link to="/methodology">Understand the cohort →</Link></section><section className="panel"><p className="eyebrow">Read before interpreting</p><h2>A prioritization score, not a safety verdict</h2><p>Scores are exploratory model outputs, not calibrated failure percentages. They do not predict accidents, roadside breakdowns or present roadworthiness.</p><p>Recurrence is descriptive history only. Its predictive value remains unvalidated.</p></section></div>
  </>;
}

function Queue() {
  const [capacity, setCapacity] = useState(40);
  const [draft, setDraft] = useState('40');
  const [offset, setOffset] = useState(0);
  const state = useData(`/api/queue?capacity=${capacity}&limit=20&offset=${offset}`);
  const invalid = !/^\d+$/.test(draft) || Number(draft) > 500;
  return <>
    <Heading eyebrow="01 / Follow-up queue" title="A bounded list. A clear priority."><p>Ranked historical index-inspection cases, not vehicle identities. Highest exploratory score first; ties use opaque case IDs, never outcomes.</p></Heading>
    <section className="panel capacity"><div><h2>Follow-up capacity</h2><p>Applies only to the 200-case demonstration. The saved 936-example evaluation never changes.</p></div><form onSubmit={event => {event.preventDefault(); if (!invalid) {setCapacity(Number(draft)); setOffset(0);}}}><label htmlFor="capacity">Number of cases to select</label><div className="input-row"><input id="capacity" type="number" min="0" max="500" step="1" value={draft} onChange={event => setDraft(event.target.value)} aria-describedby="capacity-help"/><button disabled={invalid}>Apply capacity</button></div><small id="capacity-help">0–500 requested; selection is capped at available eligible cases.</small></form></section>
    <Status state={state}>{data => <>
      <div className="queue-summary" aria-live="polite"><h2>{data.selected} selected <span>of {data.eligible} eligible cases</span></h2><span className="tag">REQUESTED {data.requested_capacity} · UNSCORED {data.unscored}</span></div>
      {data.exceeds_available && <Warning>Requested capacity exceeds available eligible cases. All {data.eligible} eligible cases are selected; no extra cases or scores are invented.</Warning>}
      {data.unscored > 0 && <Warning>{data.unscored} cases have insufficient data and are not assigned a rank. They remain available through the cases API.</Warning>}
      {data.items.length ? <section className="panel table-panel"><div className="table-scroll"><table><caption>Historical follow-up queue · as of {data.as_of} · exploratory score / 100</caption><thead><tr><th scope="col">Rank</th><th scope="col">Index-inspection case</th><th scope="col">Index date</th><th scope="col">Score / 100</th><th scope="col">Brakes advisories</th><th scope="col">All advisories</th></tr></thead><tbody>{data.items.map(item => <tr key={item.case_id}><td className="rank">{item.rank.toString().padStart(2, '0')}</td><td><Link to={`/cases/${item.case_id}`} aria-label={`Open case ${item.case_id}`}>{item.case_id} <span aria-hidden="true">↗</span></Link></td><td>{item.index_date}</td><td><strong className="score">{score(item.exploratory_prioritization_score)}</strong></td><td>{item.features.brake_advisory_count}</td><td>{item.features.advisory_count}</td></tr>)}</tbody></table></div><div className="pagination"><span>Showing {offset + 1}–{offset + data.items.length} of {data.selected} selected</span><div><button className="secondary" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous</button><button className="secondary" disabled={offset + data.items.length >= data.selected} onClick={() => setOffset(value => value + 20)}>Next</button></div></div></section> : <section className="panel state"><h2>No cases selected</h2><p>{capacity === 0 ? 'Capacity is zero. Increase it to review a ranked list.' : 'No eligible scored cases are available on this page.'}</p></section>}
      <p className="footnote">Explanatory columns are current advisory counts used by the model. Open a case for the full mathematical explanation. Subsequent outcomes are absent from this snapshot and do not affect ranking.</p>
    </>}</Status>
  </>;
}

function CaseDetail({caseId}) {
  const state = useData(`/api/cases/${caseId}`);
  return <><Link className="back" to="/queue">← Follow-up queue</Link><Heading eyebrow="02 / Index-inspection case" title="The record behind the score."><p>One case represents one index inspection. A vehicle can have multiple index inspections; this opaque case ID is not a vehicle ID.</p></Heading><Status state={state}>{data => {
    const prediction = data.prediction;
    const explanation = prediction.explanation;
    const history = data.history;
    return <>
      <div className="case-banner"><div><span className="eyebrow">CASE {data.case_id}</span><h2>Index inspection · {data.index_date}</h2><p>Class 4 · normal inspection (NT) · strict pass (P) · brakes advisory</p></div><div className="case-score"><span>Exploratory score / 100</span><strong>{score(prediction.exploratory_prioritization_score)}</strong><span>Not a calibrated failure percentage</span></div></div>
      {prediction.status !== 'scored' && <Warning><strong>{prediction.status.replaceAll('_', ' ')}</strong><p>{prediction.reasons?.join('. ')} No zero-risk score is substituted.</p></Warning>}
      <Warning>Historical case, as of {data.as_of}; not a current roadworthiness assessment. Age, mileage, inputs and history are frozen at the {data.index_date} index inspection, not updated to today.</Warning>
      <section className="panel"><p className="eyebrow">Current inspection · model inputs</p><h2>Available at the index, never after it</h2><div className="feature-grid">{Object.entries(data.inputs.features).map(([key, value]) => <div key={key}><span>{names[key] || key}</span><strong>{value === null ? 'Missing' : Number.isInteger(value) ? value.toLocaleString() : value.toFixed(1)}</strong></div>)}</div><p className="footnote">Current advisories are counts of recorded advisory (A) items, not item descriptions or mechanical diagnoses. This snapshot does not export individual item text. Minor (M) defects are not counted as advisories.</p></section>
      <section className="panel"><p className="eyebrow">Descriptive history · NOT used by the model</p><h2>Recurring advisories are context, not an explanation</h2><div className="feature-grid"><div><span>Prior recorded tests</span><strong>{history.prior_recorded_tests}</strong></div><div><span>Prior brakes-advisory tests</span><strong>{history.prior_brake_advisory_tests}</strong></div><div><span>Prior brakes-failure tests</span><strong>{history.prior_brake_failure_tests}</strong></div><div><span>Observed history length</span><strong>{history.observed_history_days} <small>days</small></strong></div></div><p>Available through {data.history_available_through}; source history begins {data.history_starts}. {data.history_resolution}.</p><p className="footnote">Recurrence’s predictive value is unvalidated. Limited recorded history is not confirmed absence of earlier advisories. A repeated family advisory does not establish ignored repairs or failure of the identical physical part.</p></section>
      {explanation && <section className="panel"><p className="eyebrow">Verified Phase 3 explanation · frozen logistic model</p><h2>A mathematical decomposition, not a causal diagnosis</h2><p>Each term is a coefficient × transformed current input, relative to training-centered values. All terms are shown, including missingness indicators. Positive terms raise the model margin; negative terms lower it.</p><div className="table-scroll"><table><caption>Exact model terms in log-odds units, not percentage points</caption><thead><tr><th scope="col">Term</th><th scope="col">Contribution to log-odds</th></tr></thead><tbody><tr><td>Intercept</td><td>{explanation.intercept_log_odds.toFixed(6)}</td></tr>{explanation.terms.map(term => <tr key={term.feature}><td>{names[term.feature] || term.feature}</td><td><span className={term.log_odds_contribution >= 0 ? 'term-positive' : ''}>{term.log_odds_contribution >= 0 ? '+' : ''}{term.log_odds_contribution.toFixed(6)}</span></td></tr>)}</tbody></table></div><p className="formula">100 × sigmoid(intercept + sum of all terms) = {score(prediction.exploratory_prioritization_score)} / 100</p><p className="footnote">Displayed terms are rounded; the API preserves full precision. Recurrence contributes no terms. Associations are not evidence of causation.</p><div className="two-col"><p><strong>Imputed inputs:</strong> {prediction.imputed_features.length ? prediction.imputed_features.join(', ') : 'None'}</p><p><strong>Outside training range:</strong> {prediction.outside_training_range.length ? prediction.outside_training_range.join(', ') + ' — extrapolation; interpret cautiously' : 'None'}</p></div></section>}
      <p className="footnote">{prediction.warning} · Model {prediction.model_version}. Subsequent outcomes are not exported here, not prediction inputs and not shown as historical context.</p>
    </>;
  }}</Status></>;
}

function Evaluation({state}) {
  const [capacityIndex, setCapacityIndex] = useState(0);
  return <><Heading eyebrow="03 / Saved evaluation" title="Inspect the evidence, not just the score."><p>Full held-out chronological cohort. These saved results never depend on which demonstration cases are selected.</p></Heading><Status state={state}>{data => {
    const primary = data.primary_temporal;
    const observed = primary.logistic;
    return <>
      <div className="stats"><Stat value={observed.examples} label="Held-out examples / vehicles">{observed.positive} positive · {observed.negative} negative · {percent(observed.positive, observed.examples)} observed prevalence</Stat><Stat value={data.training.examples} label="Training examples / vehicles">{data.training.positive} positive · {data.training.negative} negative. All training outcomes precede the freeze.</Stat><Stat value={metric(observed.average_precision)} label="Logistic average precision">Ranking metric; not accuracy or a safety probability. Exploratory, without uncertainty intervals.</Stat></div>
      <Warning>No calibration, tuning or independent model-selection partition. Brier improvement over the constant baseline is small; these results do not establish probability reliability or production readiness.</Warning>
      <section className="panel table-panel"><div className="section-pad"><p className="eyebrow">Same 936-example cohort</p><h2>Two simple baselines. One fixed candidate.</h2></div><div className="table-scroll"><table><caption>Saved full-cohort comparisons · higher average precision / lower Brier is better</caption><thead><tr><th scope="col">Method</th><th scope="col">Average precision</th><th scope="col">Brier score</th></tr></thead><tbody>{Object.entries(primary).map(([key, method]) => <tr key={key}><th scope="row">{names[key]}</th><td>{metric(method.average_precision)}</td><td>{metric(method.brier_score)}</td></tr>)}</tbody></table></div><p className="section-pad footnote">The count baseline ranks by advisory count, not a probability forecast; Brier is not applicable. Constant probability is the observed training prevalence ({percent(data.training.positive, data.training.examples)}), not holdout prevalence.</p></section>
      <section className="panel"><div className="capacity"><div><p className="eyebrow">Fixed saved operating points</p><h2>What does a limited review capacity capture?</h2></div><label>Evaluation capacity<select value={capacityIndex} onChange={event => setCapacityIndex(Number(event.target.value))}>{observed.capacities.map((point, index) => <option key={point.capacity_fraction} value={index}>{Math.round(point.capacity_fraction * 100)}% · {point.selected} of {observed.examples}</option>)}</select></label></div><p>Only predeclared 10%, 20% and 30% points are available. Selected count uses ceiling rounding. No interpolation or demo-subset recomputation.</p><div className="table-scroll"><table><caption>Saved review-capacity results · counts and percentages derived from these counts</caption><thead><tr><th scope="col">Method</th><th scope="col">Selected</th><th scope="col">Observed positive / negative selected</th><th scope="col">Precision</th><th scope="col">Recall of {observed.positive} positives</th></tr></thead><tbody>{Object.entries(primary).map(([key, method]) => {
        const point = method.capacities[capacityIndex];
        return <tr key={key}><th scope="row">{names[key]}</th><td>{point.selected}</td><td>{point.true_positives} / {point.false_positives}</td><td>{percent(point.true_positives, point.selected)}</td><td>{percent(point.true_positives, point.all_positives)}</td></tr>;
      })}</tbody></table></div><div className="bar-chart" role="img" aria-label={`Observed positives captured at saved capacity out of ${observed.positive} total positives`}>{Object.entries(primary).map(([key, method]) => {const point = method.capacities[capacityIndex]; return <div className="bar-row" key={key}><span>{names[key]}</span><div className="track"><div className="bar" style={{width: `${100 * point.true_positives / point.all_positives}%`}}/></div><strong>{point.true_positives} / {point.all_positives}</strong></div>;})}<p className="footnote">Bar scale: 0–{observed.positive} observed positives. Every bar is one saved operating point, not a fitted curve.</p></div></section>
      <section className="panel"><h2>What this evaluation cannot establish</h2><p>The primary split permits seen vehicles in principle, but actual training/evaluation vehicle overlap was {data.primary_seen_vehicle_count}. The unseen-vehicle subset is the same {observed.examples} examples, not independent confirmation.</p><p>Recurrence’s predictive value remains unvalidated. Training history was sparse and left-truncated; recurrence is excluded from the fitted model.</p><p>{data.availability}. No accident, breakdown or present-roadworthiness outcome was evaluated.</p><Link to="/methodology">Read the timeline and limitations →</Link></section>
    </>;
  }}</Status></>;
}

function Methodology({versions}) {
  const state = useData('/api/methodology');
  return <><Heading eyebrow="04 / Methodology & limitations" title="Boundaries are part of the product."><p>A reproducible retrospective study, not a production-validated safety system.</p></Heading><Status state={state}>{data => <>
    <section className="panel"><h2>The frozen evaluation timeline</h2><ol className="timeline"><li><strong>Training index inspections</strong><span>{data.protocol.training_indices.join(' → ')}</span></li><li><strong>Model freeze</strong><span>{data.protocol.freeze} · every training outcome observable before this point</span></li><li><strong>Held-out prediction dates</strong><span>{data.protocol.evaluation_indices.join(' → ')}</span></li><li><strong>Outcome observation ends</strong><span>{data.protocol.observation_end} · immediate next normal inspection within 9–15 calendar months</span></li></ol><p>Retrospective test/completion timestamps are availability proxies. Historical public-release availability at the freeze was not established.</p></section>
    <div className="two-col"><section className="panel"><h2>Target and observation</h2><p>Class 4 strict passed normal inspections (NT/P) with a recorded brake advisory (A). Outcome: a verified brake-family failure at the immediate next routine inspection in the 9–15-calendar-month window.</p><p>Do not skip an earlier routine inspection to find a later qualifying one. Retests are excluded. Missing follow-up, out-of-window tests and ambiguous joins are censored/excluded, never automatically negative.</p><p>Rectification-at-station (PRS) is not a strict-pass index; recorded brake failures at the qualifying follow-up, including PRS failure items, count under the verified source mapping.</p></section><section className="panel"><h2>Model and explanation</h2><p>Four current-inspection features: vehicle age, recorded mileage, brakes-A count and all-family A count. Training-only median imputation with missing indicators and standard scaling; fixed L2 logistic regression.</p><p>Scores preserve 100 × the frozen model’s positive-class output. They are not validated failure percentages. Explanations decompose the logistic margin, not causation.</p><p>No postcode, identifiers, recurrence, future outcome or later history is used. No automated repair decisions or high/medium/low safety tiers.</p></section></div>
    <section className="panel"><h2>History is limited; recurrence is unvalidated</h2><p>Available source history begins {versions.history_starts}. No earlier record does not prove no earlier advisory. Training had only 18 examples with prior recorded history and 14 with recorded recurrence; none had 365 days of observed history. Evaluation had more history, but cannot validate a recurrence predictor that was not trained.</p><p>The 200-case snapshot exports aggregate prior counts and duration, not a dated inspection timeline or individual advisory descriptions. Those details are intentionally not invented. Outcomes are held separately from serving data.</p><p>Recurring family advisories cannot prove an ignored repair or identify the same physical part. Performance may shift across time, vehicle mix, recording practice and mileage revisions.</p></section>
    <section className="panel"><h2>Artifact identity</h2><dl className="versions"><dt>Model</dt><dd>{versions.model_version}</dd><dt>Data</dt><dd>{versions.data_version}</dd><dt>Trusted manifest SHA256</dt><dd><code>{versions.manifest_sha256}</code></dd><dt>Demonstration</dt><dd>{versions.demo_cases} historical cases · as of {versions.as_of} · not a live fleet</dd><dt>Evaluation</dt><dd>{versions.evaluation_examples} examples · fixed saved aggregate artifacts</dd></dl><details><summary>Read the preserved model card</summary><pre className="model-card">{data.model_card}</pre></details></section>
  </>}</Status></>;
}

function App() {
  const [path, setPath] = useState(location.pathname);
  const versions = useData('/api/versions');
  const evaluation = useData('/api/evaluation');
  useEffect(() => {const update = () => setPath(location.pathname); window.addEventListener('popstate', update); return () => window.removeEventListener('popstate', update);}, []);
  useEffect(() => {document.getElementById('main')?.focus();}, [path]);
  const navigation = [['/', 'Overview', '00'], ['/queue', 'Follow-up queue', '01'], ['/evaluation', 'Evaluation', '03'], ['/methodology', 'Methodology', '04']];
  return <div className="app"><a className="skip" href="#main">Skip to content</a><aside className="sidebar"><Link to="/" className="brand"><span className="brand-icon" aria-hidden="true">B/P</span><span>BEYOND<br/>THE PASS<span className="brand-subtitle">ADVISORY FOLLOW-UP</span></span></Link><nav aria-label="Main navigation">{navigation.map(([to, label, number]) => <Link key={to} to={to} className={path === to || to === '/queue' && path.startsWith('/cases/') ? 'active' : ''} aria-current={path === to ? 'page' : undefined}><span>{number}</span>{label}</Link>)}</nav><div className="sidebar-note"><span className="status-dot"/> EXPLORATORY RELEASE<p>Recorded test outcomes.<br/>Not a safety classification.</p><span className="mini-rule"/><p>Python · scikit-learn<br/>FastAPI · React<br/>Read-only SQLite</p></div></aside><div className="workspace"><div className="topbar"><span>AUTOMOTIVE / DATA SCIENCE PORTFOLIO</span><span className="tag">HISTORICAL · NOT LIVE</span></div><main id="main" tabIndex="-1"><Status state={versions}>{data => <><div className="context">DVSA anonymised MOT data <span>•</span> As of {data.as_of} <span>•</span> Brakes / Class 4</div>{path === '/' ? <Overview versions={data} evaluation={evaluation}/> : path === '/queue' ? <Queue/> : path.startsWith('/cases/') ? <CaseDetail caseId={path.split('/')[2]}/> : path === '/evaluation' ? <Evaluation state={evaluation}/> : path === '/methodology' ? <Methodology versions={data}/> : <section className="panel"><h1>Page not found</h1><Link to="/">Return to overview</Link></section>}</>}</Status></main><footer>Contains DVSA data under the <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">Open Government Licence v3.0</a>. <span>Beyond the Pass · Exploratory, retrospective research</span></footer></div></div>;
}

createRoot(document.getElementById('root')).render(<App/>);
