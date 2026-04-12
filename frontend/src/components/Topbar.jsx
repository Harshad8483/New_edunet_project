import React from 'react';
import { motion } from 'framer-motion';
import { Bell, Search, User } from 'lucide-react';

const Topbar = ({ title }) => {
    return (
        <motion.header
            initial={{ y: -100 }}
            animate={{ y: 0 }}
            className="h-20 bg-slate-900/50 backdrop-blur-xl border-b border-white/5 sticky top-0 z-40 px-8 flex items-center justify-between"
        >
            <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">{title}</h2>
                <p className="text-sm text-slate-400 mt-1">Smart Electricity Analysis</p>
            </div>

            <div className="flex items-center gap-3 bg-slate-800/50 px-4 py-2 rounded-full border border-white/5">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                <p className="text-sm font-medium text-slate-300">
                    {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                </p>
            </div>
        </motion.header>
    );
};

export default Topbar;
