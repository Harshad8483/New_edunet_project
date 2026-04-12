import React from 'react';
import { motion } from 'framer-motion';
import { LayoutDashboard, PieChart, Zap, Info, LogOut } from 'lucide-react';

const Sidebar = ({ activeTab, setActiveTab }) => {
    const menuItems = [
        { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
        { id: 'analysis', label: 'Analysis', icon: PieChart },
        { id: 'prediction', label: 'Forecast', icon: Zap },
        { id: 'about', label: 'About', icon: Info },
    ];

    return (
        <motion.aside
            initial={{ x: -250 }}
            animate={{ x: 0 }}
            className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-screen fixed left-0 top-0 z-50 shadow-2xl"
        >
            <div className="p-8 pb-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                    <Zap className="text-white w-6 h-6 fill-current" />
                </div>
                <div>
                    <h1 className="text-xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                        GreenAI
                    </h1>
                    <p className="text-xs text-slate-500 font-medium tracking-wider">ENERGY ANALYZER</p>
                </div>
            </div>

            <div className="px-4 py-6 flex-1 space-y-2">
                {menuItems.map((item) => (
                    <button
                        key={item.id}
                        onClick={() => setActiveTab(item.id)}
                        className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-xl transition-all duration-300 group relative overflow-hidden ${activeTab === item.id
                            ? 'bg-gradient-to-r from-emerald-500/10 to-teal-500/5 text-emerald-400 font-semibold shadow-inner border border-white/5'
                            : 'text-slate-400 hover:text-white hover:bg-white/5'
                            }`}
                    >
                        {activeTab === item.id && (
                            <motion.div
                                layoutId="activeTabIndicator"
                                className="absolute left-0 w-1 h-8 bg-emerald-500 rounded-r-full"
                            />
                        )}
                        <item.icon size={20} className={`transition-transform duration-300 ${activeTab === item.id ? 'scale-110' : 'group-hover:scale-110'}`} />
                        <span>{item.label}</span>
                    </button>
                ))}
            </div>

            {/* Footer removed as per request */}
            <div className="p-4 border-t border-slate-800 opacity-0 pointer-events-none">
            </div>
        </motion.aside>
    );
};

export default Sidebar;
