import React from 'react';
import {
    LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart
} from 'recharts';
import { motion } from 'framer-motion';

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-slate-800 border border-slate-700 p-4 rounded-lg shadow-xl">
                <p className="text-slate-400 text-xs mb-2">{label}</p>
                <p className="text-white font-bold text-lg">
                    {payload[0].value.toFixed(2)}
                    <span className="text-emerald-400 text-sm ml-1">kWh</span>
                </p>
            </div>
        );
    }
    return null;
};

const UsageChart = ({ data, type = 'line', hideHeader = false }) => {
    const [timeRange, setTimeRange] = React.useState('Monthly');

    // Filter data based on selection
    const filteredData = React.useMemo(() => {
        if (!data || data.length === 0) return [];
        let days = 30;
        if (timeRange === 'Weekly') days = 7;
        if (timeRange === 'Yearly') days = 365;

        // The last data point time
        const lastDate = new Date(data[data.length - 1].date);
        const cutoffDate = new Date(lastDate);
        cutoffDate.setDate(cutoffDate.getDate() - days);

        const validData = data.filter(d => {
            const dt = new Date(d.date).getTime();
            return dt >= cutoffDate.getTime();
        });

        const firstDt = validData.length > 0 ? new Date(validData[0].date).getTime() : 0;
        const lastDt = validData.length > 0 ? new Date(validData[validData.length - 1].date).getTime() : 0;
        const actualSpanDays = validData.length > 1 ? (lastDt - firstDt) / (1000 * 60 * 60 * 24) : 0;

        return validData.map(d => {
            const dateObj = new Date(d.date);
            let displayDate = "";
            if (actualSpanDays <= 14) {
                // Detailed view for short periods (up to 2 weeks)
                displayDate = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric',  hour: '2-digit', minute: '2-digit', hour12: false }).format(dateObj);
            } else if (actualSpanDays <= 180) {
                // Day and Month for medium periods
                displayDate = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(dateObj);
            } else {
                // Month and Year for long periods
                displayDate = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(dateObj);
            }
            
            return {
                ...d,
                displayDate
            };
        });
    }, [data, timeRange]);

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            className="bg-slate-800/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl"
        >
            {!hideHeader && (
                <div className="flex justify-between items-center mb-6">
                    <div>
                        <h3 className="text-lg font-bold text-white">Consumption Overview</h3>
                        <p className="text-sm text-slate-400">Trend analysis over time ({timeRange})</p>
                    </div>
                    <select
                        value={timeRange}
                        onChange={(e) => setTimeRange(e.target.value)}
                        className="bg-slate-900 border border-slate-700 text-slate-300 text-sm rounded-lg p-2 focus:ring-2 focus:ring-emerald-500/50 outline-none cursor-pointer hover:bg-slate-800 transition-colors"
                    >
                        <option value="Weekly">Last 7 Days</option>
                        <option value="Monthly">Last 30 Days</option>
                        <option value="Yearly">Last Year</option>
                    </select>
                </div>
            )}

            <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    {type === 'line' ? (
                        <AreaChart data={filteredData} margin={{ top: 10, right: 10, left: 20, bottom: 20 }}>
                            <defs>
                                <linearGradient id="colorUsage" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                            <XAxis dataKey="displayDate" stroke="#94a3b8" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} minTickGap={30} label={{ value: 'Time (Days/Months/Years)', position: 'bottom', offset: 0, fill: '#94a3b8', fontSize: 12 }} />
                            <YAxis domain={['auto', 'auto']} stroke="#94a3b8" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} label={{ value: 'Electricity Usage (kWh)', angle: -90, position: 'insideLeft', offset: -10, fill: '#94a3b8', fontSize: 12 }} />
                            <Tooltip content={<CustomTooltip />} />
                            <Area
                                type="monotone"
                                dataKey="usage"
                                stroke="#10b981"
                                strokeWidth={3}
                                fillOpacity={1}
                                fill="url(#colorUsage)"
                            />
                        </AreaChart>
                    ) : (
                        <BarChart data={filteredData} margin={{ top: 10, right: 10, left: 20, bottom: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                            <XAxis dataKey="displayDate" stroke="#94a3b8" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} minTickGap={30} label={{ value: 'Time (Days/Months/Years)', position: 'bottom', offset: 0, fill: '#94a3b8', fontSize: 12 }} />
                            <YAxis domain={['auto', 'auto']} stroke="#94a3b8" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} label={{ value: 'Electricity Usage (kWh)', angle: -90, position: 'insideLeft', offset: -10, fill: '#94a3b8', fontSize: 12 }} />
                            <Tooltip content={<CustomTooltip />} />
                            <Bar dataKey="usage" fill="#34d399" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    )}
                </ResponsiveContainer>
            </div>
        </motion.div>
    );
};

export default UsageChart;
