import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../../lib/helpers';
import { useAtlas } from '../../store/atlasStore';

export function ExperimentResults({ experimentId }) {
    const [experiment, setExperiment] = useState(null);
    const [loading, setLoading] = useState(true);
    const { dispatch } = useAtlas();

    useEffect(() => {
        if (!experimentId) return;
        setLoading(true);
        axios.get(`${API}/learning/experiments/${experimentId}`)
            .then(res => {
                setExperiment(res.data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, [experimentId]);

    const handleDeploy = () => {
        if (experiment?.model_ids?.length > 0) {
            sessionStorage.setItem("atlas_prefill_model_id", experiment.model_ids[0]);
        }
        dispatch({ type: "SET_PROJECT_TAB", payload: "paper" });
    };

    if (!experimentId) return null;
    if (loading) return <div style={{ color: 'var(--text-secondary)', padding: 16 }}>Loading experiment metrics...</div>;
    if (!experiment) return <div style={{ color: 'var(--amber)', padding: 16 }}>Failed to load experiment.</div>;

    const aggregate = experiment.aggregate || {};

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-dim)', borderRadius: 8, padding: 32, position: 'relative' }}>
                <div style={{ position: 'absolute', top: 24, right: 32 }}>
                    <button 
                        onClick={handleDeploy}
                        style={{ 
                            background: 'var(--green)', 
                            color: '#000', 
                            border: 'none', padding: '10px 16px', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer'
                        }}
                    >
                        Deploy to Paper Trading
                    </button>
                </div>
                
                <h3 style={{ fontSize: 18, margin: '0 0 8px 0', color: 'var(--text-primary)', paddingRight: 200 }}>
                    {experiment.name || "Unnamed Experiment"}
                </h3>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 24, borderBottom: '1px solid var(--border-dim)', paddingBottom: 16 }}>
                    ID: <span style={{ fontFamily: 'var(--font-mono)' }}>{experimentId}</span> · Status: <span style={{ textTransform: 'uppercase', color: experiment.status === 'done' ? 'var(--green)' : 'var(--amber)' }}>{experiment.status}</span>
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                    <div style={{ padding: 20, background: 'var(--bg-elevated)', borderRadius: 8, border: '1px solid var(--border-dim)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>Accuracy (Avg)</div>
                        <div style={{ fontSize: 24, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                            {aggregate.accuracy_mean !== undefined ? (aggregate.accuracy_mean * 100).toFixed(1) + '%' : '—'}
                        </div>
                    </div>
                    <div style={{ padding: 20, background: 'var(--bg-elevated)', borderRadius: 8, border: '1px solid var(--border-dim)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>F1 Score (Avg)</div>
                        <div style={{ fontSize: 24, fontFamily: 'var(--font-mono)', color: 'var(--blue-400)' }}>
                            {aggregate.f1_mean !== undefined ? (aggregate.f1_mean * 100).toFixed(1) + '%' : '—'}
                        </div>
                    </div>
                    <div style={{ padding: 20, background: 'var(--bg-elevated)', borderRadius: 8, border: '1px solid var(--border-dim)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>ROC AUC (Avg)</div>
                        <div style={{ fontSize: 24, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                            {aggregate.roc_auc_mean !== undefined ? (aggregate.roc_auc_mean * 100).toFixed(1) + '%' : '—'}
                        </div>
                    </div>
                </div>
            </div>

            {experiment.folds && experiment.folds.length > 0 && (
                <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-dim)', borderRadius: 8, padding: 32 }}>
                    <h3 style={{ fontSize: 16, margin: '0 0 24px 0', color: 'var(--text-primary)' }}>Walk-Forward CV Folds</h3>
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: 13 }}>
                            <thead>
                                <tr>
                                    <th style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', color: 'var(--text-secondary)' }}>Fold #</th>
                                    <th style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', color: 'var(--text-secondary)' }}>Accuracy</th>
                                    <th style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', color: 'var(--text-secondary)' }}>F1</th>
                                    <th style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', color: 'var(--text-secondary)' }}>ROC-AUC</th>
                                </tr>
                            </thead>
                            <tbody>
                                {experiment.folds.map(f => (
                                    <tr key={f.fold}>
                                        <td style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', color: 'var(--text-primary)' }}>{f.fold}</td>
                                        <td style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                                            {f.metrics?.accuracy !== undefined ? (f.metrics.accuracy * 100).toFixed(1) + '%' : '—'}
                                        </td>
                                        <td style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                                            {f.metrics?.f1 !== undefined ? (f.metrics.f1 * 100).toFixed(1) + '%' : '—'}
                                        </td>
                                        <td style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                                            {f.metrics?.roc_auc !== undefined ? (f.metrics.roc_auc * 100).toFixed(1) + '%' : '—'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

