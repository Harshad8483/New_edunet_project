import React, { useRef, useState, useEffect } from 'react';
import { motion } from 'framer-motion';

const KPICard = ({ title, value, subtext, icon: Icon, delay = 0 }) => {
    const [count, setCount] = useState(0);
    const controls = useRef(null);

    useEffect(() => {
        // Simple count-up animation for numbers
        const numValue = parseFloat(value.replace(/[^0-9.]/g, ''));
        if (!isNaN(numValue)) {
            let start = 0;
            const end = numValue;
            const duration = 2000;
            const increment = end / (duration / 16);

            const timer = setInterval(() => {
                start += increment;
                if (start >= end) {
                    setCount(end);
                    clearInterval(timer);
                } else {
                    setCount(start);
                }
            }, 16);
            return () => clearInterval(timer);
        }
    }, [value]);

    const displayValue = !isNaN(parseFloat(value.replace(/[^0-9.]/g, '')))
        ? value.replace(/[\d.]+/, count.toFixed(value.includes('.') ? 2 : 0))
        : value;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay }}
            className="bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl p-6 shadow-xl hover:shadow-2xl hover:bg-white/15 transition-all duration-300 group"
        >
            <div className="flex justify-between items-start">
                <div>
                    <p className="text-slate-400 text-sm font-medium mb-1">{title}</p>
                    <h3 className="text-3xl font-bold text-white tracking-tight group-hover:scale-105 transition-transform origin-left">
                        {displayValue}
                    </h3>
                </div>
                <div className="p-3 bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-xl group-hover:from-emerald-500/30 group-hover:to-teal-500/30 transition-colors">
                    <Icon className="w-6 h-6 text-emerald-400" />
                </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
                <span className={`font-medium ${subtext.includes('Improvement') ? 'text-rose-400' : 'text-emerald-400'}`}>
                    {subtext}
                </span>
            </div>
        </motion.div>
    );
};

export default KPICard;
