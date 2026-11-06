import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../../lib/helpers';

export function FeatureSelector({ selectedFeatures, onChange }) {
    const [availableFeatures, setAvailableFeatures] = useState([]);

    useEffect(() => {
        axios.get(`${API}/registry/features`)
            .then(res => setAvailableFeatures(res.data || []))
            .catch(console.error);
    }, []);

    const toggleFeature = (featId) => {
        if (selectedFeatures.includes(featId)) {
            onChange(selectedFeatures.filter(id => id !== featId));
        } else {
            onChange([...selectedFeatures, featId]);
        }
    };

    return (
        <div style={{ marginTop: 8 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {availableFeatures.map(feat => {
                    const isSelected = selectedFeatures.includes(feat.id);
                    return (
                        <div 
                            key={feat.id} 
                            style={{ 
                                background: isSelected ? 'var(--blue-900)' : 'var(--bg-base)', 
                                border: `1px solid ${isSelected ? 'var(--blue-500)' : 'var(--bg-border)'}`, 
                                borderRadius: 8, padding: 16, cursor: 'pointer', transition: 'all 0.2s'
                            }}
                            onClick={() => toggleFeature(feat.id)}
                        >
                            <div style={{ fontWeight: 500, color: isSelected ? 'var(--blue-400)' : 'var(--text-primary)', marginBottom: 4 }}>{feat.name}</div>
                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>{feat.description}</div>
                            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)', background: 'rgba(0,0,0,0.2)', padding: '2px 6px', borderRadius: 4, display: 'inline-block' }}>
                                Params: {(feat.params || []).join(', ')}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

