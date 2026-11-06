import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../../lib/helpers';

const MODEL_OPTIONS = [
  { value: 'logreg',   label: 'Logistic Regression', desc: 'Fast, interpretable baseline' },
  { value: 'xgboost',  label: 'XGBoost',              desc: 'Gradient-boosted trees (recommended)' },
  { value: 'randomforest',       label: 'Random Forest',         desc: 'Ensemble of decision trees' },
  { value: 'lstm',     label: 'LSTM (Neural Net)',      desc: 'Sequential deep learning (slow)' },
];

function StatusBadge({ status }) {
  const colors = {
    running:   { bg: '#1c3a4a', color: '#38bdf8' },
    done:      { bg: '#1a3a2a', color: '#4ade80' },
    failed:    { bg: '#3a1a1a', color: '#f87171' },
    queued:    { bg: '#2a2a1a', color: '#fbbf24' },
  };
  const c = colors[status] || { bg: '#222', color: '#aaa' };
  return (
    <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4,
      background: c.bg, color: c.color, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>
      {status}
    </span>
  );
}

function MetricCard({ label, value }) {
  return (
    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-dim)',
      borderRadius: 6, padding: '12px 16px', textAlign: 'center' }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
        {value !== undefined && value !== null ? (typeof value === 'number' ? (value * 100).toFixed(1) + '%' : value) : '—'}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>{label}</div>
    </div>
  );
}

export function CreateExperiment({ project }) {
  const [datasets, setDatasets] = useState([]);
  const [loadingDs, setLoadingDs] = useState(true);

  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [expName, setExpName] = useState('');
  const [modelKind, setModelKind] = useState('xgboost');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [runningExp, setRunningExp] = useState(null);   // the live experiment object
  const [polling, setPolling] = useState(false);

  // ── Load saved datasets ──────────────────────────────────────────────
  useEffect(() => {
    axios.get(`${API}/learning/datasets`)
      .then(r => setDatasets(r.data || []))
      .catch(() => setDatasets([]))
      .finally(() => setLoadingDs(false));
  }, []);

  // ── Auto-name experiment when dataset or model changes ───────────────
  useEffect(() => {
    const ds = datasets.find(d => d.dataset_id === selectedDatasetId);
    if (ds && modelKind) {
      setExpName(`${ds.symbol} ${ds.interval} – ${modelKind} (h=${ds.spec?.horizon})`);
    }
  }, [selectedDatasetId, modelKind, datasets]);

  // ── Poll running experiment ──────────────────────────────────────────
  const pollExperiment = useCallback(async (id) => {
    try {
      const r = await axios.get(`${API}/learning/experiments/${id}`);
      setRunningExp(r.data);
      if (r.data.status === 'running' || r.data.status === 'queued') {
        setTimeout(() => pollExperiment(id), 2500);
      } else {
        setPolling(false);
      }
    } catch {
      setPolling(false);
    }
  }, []);

  // ── Submit ───────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    const ds = datasets.find(d => d.dataset_id === selectedDatasetId);
    if (!ds) return;
    setSubmitting(true);
    setError(null);
    setRunningExp(null);

    const payload = {
      name: expName,
      provider: ds.provider,
      symbol: ds.symbol,
      interval: ds.interval,
      period: ds.period,
      tags: project?._id ? [project._id] : [],
      dataset: {
        feature_ids: ds.spec.feature_ids,
        horizon: ds.spec.horizon,
        label_kind: ds.spec.label_kind,
        label_params: ds.spec.label_params || {},
        min_history: ds.spec.min_history || 100,
        regime_filter: ds.spec.regime_filter || false,
      },
      model: { kind: modelKind },
    };

    try {
      const r = await axios.post(`${API}/learning/experiments/run`, payload);
      setRunningExp(r.data);
      setPolling(true);
      setTimeout(() => pollExperiment(r.data.experiment_id), 2500);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail) || err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const selectedDs = datasets.find(d => d.dataset_id === selectedDatasetId);

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* ── Config card ─────────────────────────────────────────────── */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-dim)', borderRadius: 8, padding: 28 }}>
        <div className="sys-label" style={{ marginBottom: 20 }}>New Experiment</div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Dataset selector */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Dataset
            </label>
            {loadingDs ? (
              <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>Loading saved datasets…</div>
            ) : datasets.length === 0 ? (
              <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
                No datasets found. Go to <b>Datasets</b> and build one first.
              </div>
            ) : (
              <select
                required
                value={selectedDatasetId}
                onChange={e => setSelectedDatasetId(e.target.value)}
                style={{ background: 'var(--bg-base)', border: '1px solid var(--border-dim)',
                  color: 'var(--text-primary)', padding: '10px 12px', borderRadius: 6, fontSize: 13 }}
              >
                <option value="">— Select a dataset —</option>
                {datasets.map(ds => (
                  <option key={ds.dataset_id} value={ds.dataset_id}>
                    {ds.symbol} · {ds.interval} · {ds.period} · {ds.n_rows} rows · {ds.n_features} features
                    &nbsp;({ds.spec?.label_kind}, h={ds.spec?.horizon})
                  </option>
                ))}
              </select>
            )}

            {/* Dataset info pill row */}
            {selectedDs && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
                {[
                  `${selectedDs.n_rows} rows`,
                  `${selectedDs.n_features} features`,
                  `horizon ${selectedDs.spec?.horizon}`,
                  selectedDs.spec?.label_kind,
                  selectedDs.provider,
                ].map(t => (
                  <span key={t} className="badge badge-inactive" style={{ fontSize: 11 }}>{t}</span>
                ))}
              </div>
            )}
          </div>

          {/* Model selector */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Model
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
              {MODEL_OPTIONS.map(m => (
                <div key={m.value}
                  onClick={() => setModelKind(m.value)}
                  style={{
                    padding: '12px 16px', borderRadius: 6, cursor: 'pointer',
                    background: modelKind === m.value ? 'var(--bg-elevated)' : 'var(--bg-base)',
                    border: `1px solid ${modelKind === m.value ? 'var(--blue-500)' : 'var(--border-dim)'}`,
                    transition: 'border-color 0.15s',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{m.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3 }}>{m.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Experiment name */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Experiment Name
            </label>
            <input
              required
              value={expName}
              onChange={e => setExpName(e.target.value)}
              placeholder="Give this run a name…"
              style={{ background: 'var(--bg-base)', border: '1px solid var(--border-dim)',
                color: 'var(--text-primary)', padding: '10px 12px', borderRadius: 6, fontSize: 13 }}
            />
          </div>

          {error && (
            <div style={{ background: '#3a1a1a', border: '1px solid var(--red)', borderRadius: 6,
              padding: '10px 14px', color: 'var(--red)', fontSize: 13 }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !selectedDatasetId}
            className="btn btn-primary"
            style={{ alignSelf: 'flex-start', padding: '10px 28px', fontSize: 14 }}
          >
            {submitting ? 'Starting…' : '▶  Train Model'}
          </button>
        </form>
      </div>

      {/* ── Results card ─────────────────────────────────────────────── */}
      {runningExp && (
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-dim)', borderRadius: 8, padding: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
            <div className="sys-label">Training Results</div>
            <StatusBadge status={runningExp.status} />
            {polling && (
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Live updating…</span>
            )}
          </div>

          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 16 }}>
            {runningExp.experiment_id}
          </div>

          {/* Metrics grid — backend returns aggregate (cross-fold means) */}
          {runningExp.aggregate && Object.keys(runningExp.aggregate).length > 0 && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
                <MetricCard label="Accuracy (avg)"  value={runningExp.aggregate.accuracy_mean} />
                <MetricCard label="F1 Score (avg)"  value={runningExp.aggregate.f1_mean} />
                <MetricCard label="Precision (avg)" value={runningExp.aggregate.precision_mean} />
                <MetricCard label="ROC AUC (avg)"   value={runningExp.aggregate.roc_auc_mean} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
                <MetricCard label="Recall (avg)"    value={runningExp.aggregate.recall_mean} />
                <MetricCard label="IC (avg)"        value={runningExp.aggregate.information_coefficient_mean} />
                <MetricCard label="Folds"           value={`${runningExp.aggregate.n_folds ?? '—'}`} />
              </div>
              {/* Per-fold table */}
              {runningExp.folds?.length > 0 && (
                <div style={{ overflowX: 'auto', marginBottom: 12 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr>
                        {['Fold','Train','Test','Accuracy','F1','AUC','Precision','Recall'].map(h => (
                          <th key={h} style={{ textAlign: 'left', padding: '6px 10px',
                            borderBottom: '1px solid var(--border-dim)', color: 'var(--text-tertiary)',
                            fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {runningExp.folds.map(f => (
                        <tr key={f.fold} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                          <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{f.fold + 1}</td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-tertiary)', fontSize: 11 }}>{f.n_train}</td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-tertiary)', fontSize: 11 }}>{f.n_test}</td>
                          {['accuracy','f1','roc_auc','precision','recall'].map(k => (
                            <td key={k} style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>
                              {f.metrics?.[k] !== undefined ? (f.metrics[k] * 100).toFixed(1) + '%' : '—'}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {/* Top features */}
              {runningExp.folds?.[runningExp.folds.length - 1]?.top_features?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', textTransform: 'uppercase',
                    letterSpacing: 1, marginBottom: 8 }}>Top Features (Last Fold)</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {runningExp.folds[runningExp.folds.length - 1].top_features.map(f => (
                      <span key={f.id} className="badge badge-inactive" style={{ fontSize: 11 }}>
                        {f.id.split('.').slice(-1)[0]} {(f.importance * 100).toFixed(1)}%
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {runningExp.status === 'running' && (
            <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
              ⏳ Training in progress — this may take a few minutes for large datasets…
            </div>
          )}

          {runningExp.status === 'failed' && (
            <div style={{ color: 'var(--red)', fontSize: 13 }}>
              Training failed: {runningExp.error || 'Unknown error'}
            </div>
          )}

          {runningExp.status === 'done' && (
            <div style={{ color: 'var(--green, #4ade80)', fontSize: 13 }}>
              ✓ Model trained and saved. You can now run a Backtest.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
