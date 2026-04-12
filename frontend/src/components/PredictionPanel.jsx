import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Leaf, Activity, Clock, Thermometer } from 'lucide-react';

const API_BASE_URL = 'https://electricity-backend-7xea.onrender.com';

const InsightCard = ({ icon, title, primary, secondary }) => (
    <div className="p-4 bg-slate-900/50 rounded-xl border border-white/5 w-full">
        <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-white/5 text-emerald-400">{icon}</div>
            <div>
                <p className="text-xs text-slate-400">{title}</p>
                <p className="font-bold text-white">{primary}</p>
                {secondary && <p className="text-xs text-slate-400 mt-1">{secondary}</p>}
            </div>
        </div>
    </div>
);

const PredictionPanel = ({ prediction }) => {
    const [insights, setInsights] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let mounted = true;
        const fetchInsights = async () => {
            try {
                const res = await axios.get(`${API_BASE_URL}/api/insights`);
                if (mounted) setInsights(res.data);
            } catch (err) {
                console.error('Could not load insights', err);
                if (mounted) setInsights(null);
            } finally {
                if (mounted) setLoading(false);
            }
        };
        fetchInsights();
        return () => { mounted = false; };
    }, [prediction]);

    if (!prediction) return null;

    const scoreVal = Number.isFinite(prediction?.green_score) ? prediction.green_score : 0;
    const scoreColor = scoreVal > 75 ? 'text-emerald-400' :
        scoreVal > 50 ? 'text-amber-400' : 'text-rose-400';

    const strokeColor = scoreVal > 75 ? '#34d399' :
        scoreVal > 50 ? '#fbbf24' : '#fb7185';

    // Prefer monthly estimate when available; otherwise show per-reading estimate
    const estAmount = Number.isFinite(prediction?.estimated_monthly_bill_inr) ? prediction.estimated_monthly_bill_inr : prediction?.estimated_bill_inr;
    const estBillFormatted = Number.isFinite(estAmount) ?
        new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(estAmount) : '—';

    return (
        <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-slate-800/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col justify-between"
        >
            <div>
                <h3 className="text-lg font-bold text-white mb-6">AI Insights</h3>

                <div className="flex flex-col items-center justify-center py-6">
                    <div className="relative w-32 h-32 flex items-center justify-center">
                        {/* SVG Circle Gauge: use viewBox to prevent clipping and allow scaling */}
                        <svg viewBox="0 0 160 160" className="w-full h-full overflow-visible transform -rotate-90">
                            <circle
                                cx="80"
                                cy="80"
                                r="70"
                                stroke="#1e293b"
                                strokeWidth="12"
                                fill="none"
                            />
                            <motion.circle
                                initial={{ pathLength: 0 }}
                                animate={{ pathLength: (Number.isFinite(prediction.green_score) ? prediction.green_score / 100 : 0) }}
                                transition={{ duration: 1.5, ease: "easeOut" }}
                                cx="80"
                                cy="80"
                                r="70"
                                stroke={strokeColor}
                                strokeWidth="12"
                                fill="none"
                                strokeLinecap="round"
                                strokeDasharray="440"
                                strokeDashoffset="0"
                            />
                        </svg>
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <Leaf className={`w-8 h-8 mb-1 ${scoreColor}`} />
                            <span className={`text-4xl font-bold ${scoreColor}`}>
                                {Number.isFinite(prediction.green_score) ? prediction.green_score.toFixed(0) : '—'}
                            </span>
                        </div>
                    </div>
                    {/* Label placed under the circular gauge to avoid overlap */}
                    <div className="mt-2 text-center">
                        <span className="text-xs text-slate-400 font-medium uppercase tracking-wide">Green Score</span>
                    </div>
                </div>

                {/* Insight cards */}
                <div className="grid grid-cols-1 gap-3 mb-3">
                    {loading && (
                        <div className="text-sm text-slate-400">Loading insights...</div>
                    )}

                    {!loading && insights && (
                        <>
                            <InsightCard
                                icon={<Clock size={18} className="text-emerald-300" />}
                                title="Peak Usage Time"
                                primary={`${insights.peak_message}`}
                                secondary={`Peak hour: ${insights.peak_hour}:00 — Avg: ${insights.peak_hour_avg?.toFixed(2) ?? '...'} kWh`}
                            />

                            <InsightCard
                                icon={<Thermometer size={18} className="text-purple-300" />}
                                title="Environmental Impact"
                                primary={`${insights.env_message}`}
                                secondary={`Change: ${insights.env_pct_change}%`}
                            />
                        </>
                    )}

                    {!loading && !insights && (
                        <div className="text-sm text-slate-400">Could not compute insights.</div>
                    )}
                </div>

            </div>

            <div className="space-y-4 mt-4">
                <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-xl border border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                            <span className="font-bold">₹</span>
                        </div>
                        <div>
                            <p className="text-xs text-slate-400">Est. Monthly Bill (INR)</p>
                            <p className="font-bold text-white">{estBillFormatted}</p>
                        </div>
                    </div>
                </div>

                <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-xl border border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">
                            <Activity size={20} />
                        </div>
                        <div>
                            <p className="text-xs text-slate-400">Monthly CO2 Impact</p>
                            <p className="font-bold text-white">{prediction.co2_emissions?.toFixed(2) ?? '...'} kg</p>
                        </div>
                    </div>
                </div>
            </div>
        </motion.div>
    );
};

export default PredictionPanel;
