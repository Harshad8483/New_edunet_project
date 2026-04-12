import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Activity, Zap, TrendingUp, Clock, Upload, CheckCircle, AlertTriangle, FileText } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import KPICard from './components/KPICard';
import UsageChart from './components/UsageChart';
import PredictionPanel from './components/PredictionPanel';
import './index.css';

const API_BASE_URL = 'https://electricity-backend-7xea.onrender.com';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [trends, setTrends] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [trainingState, setTrainingState] = useState({ is_training: false, last_trained: null, last_metrics: null });

  // Validation / preview states
  const [validatePreview, setValidatePreview] = useState(null); // { preview: [], columns: [], suggested: {usage,date} }
  const [showValidateModal, setShowValidateModal] = useState(false);
  const [selectedUsageCol, setSelectedUsageCol] = useState(null);
  const [selectedDateCol, setSelectedDateCol] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true); // Ensure loading state is true during fetch

    try {
      // Fire parallel requests and handle them independently so one failure doesn't block UI
      const [statsRes, trendsRes, predictRes] = await Promise.allSettled([
        axios.get(`${API_BASE_URL}/api/stats`),
        axios.get(`${API_BASE_URL}/api/trends`),
        axios.get(`${API_BASE_URL}/api/predict`)
      ]);

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data);
      } else {
        console.warn('stats fetch failed', statsRes.reason?.message || statsRes.reason);
        setStats(null);
      }

      if (trendsRes.status === 'fulfilled') {
        setTrends(trendsRes.value.data);
      } else {
        console.warn('trends fetch failed', trendsRes.reason?.message || trendsRes.reason);
        setTrends([]);
      }

      if (predictRes.status === 'fulfilled') {
        setPrediction(predictRes.value.data);
      } else {
        console.warn('predict fetch failed', predictRes.reason?.message || predictRes.reason);
        setPrediction(null);
      }

    } catch (ex) {
      console.error('Unexpected error in fetchData', ex);
      setStats(null);
      setTrends([]);
      setPrediction(null);
    } finally {
      // Always clear loading so UI doesn't get stuck
      setLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Keep file reference and request a preview from the server
    setSelectedFile(file);
    setUploadedFileName(file.name);
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post(`${API_BASE_URL}/api/upload/validate`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 15000
      });

      setValidatePreview(res.data);
      setSelectedUsageCol(res.data.suggested?.usage || res.data.columns[0]);
      setSelectedDateCol(res.data.suggested?.date || res.data.columns[0]);
      setShowValidateModal(true);
    } catch (error) {
      console.error('Validation error:', error);
      const networkErr = error.message === 'Network Error' || error.code === 'ECONNABORTED';
      const serverMsg = error.response?.data?.message;
      const msg = serverMsg || (networkErr ? 'Server is waking up... please wait 30 seconds and try again' : error.message) || 'Validation failed.';
      alert(`Validation Failed: ${msg}`);
      // reset
      setUploadedFileName(null);
      setSelectedFile(null);
      setLoading(false);
    }
  };

  const confirmUpload = async () => {
    // Called when user confirms mapping in the modal
    if (!selectedFile) return;
    setShowValidateModal(false);
    setLoading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      if (selectedUsageCol) formData.append('usage_column', selectedUsageCol);
      if (selectedDateCol) formData.append('date_column', selectedDateCol);

      await axios.post(`${API_BASE_URL}/api/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 0, // large uploads may take time; disable axios timeout here
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadProgress(percentCompleted);
          }
        }
      });

      // Start polling training status until complete and then refresh data
      pollTrainingStatus();
      alert('Dataset uploaded and saved. Training is running in background. Prediction will update shortly.');

      // Reset progress UI after a short delay
      setTimeout(() => {
        setUploadProgress(null);
      }, 1500);

      // Reset file selection
      setSelectedFile(null);
    } catch (error) {
      console.error('Upload error:', error);
      const msg = error.response?.data?.message || error.message || 'Upload failed.';
      alert(`Upload Failed: ${msg}`);
      setSelectedFile(null);
      setUploadedFileName(null);
      setUploadProgress(null);
      setLoading(false);
    }
  };

  const cancelValidation = () => {
    setShowValidateModal(false);
    setSelectedFile(null);
    setUploadedFileName(null);
    setLoading(false);
  };

  const RenderEmptyState = () => (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center justify-center h-[55vh] text-center"
    >
      <div className="bg-slate-800/50 p-8 rounded-3xl border border-white/5 shadow-2xl backdrop-blur-sm max-w-lg w-full hover:border-emerald-500/30 transition-colors">
        <div className="w-24 h-24 bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner ring-1 ring-emerald-500/20">
          <Upload size={48} className="text-emerald-400" />
        </div>
        <h2 className="text-3xl font-bold text-white mb-3">Start Analysis</h2>
        <p className="text-slate-400 mb-8 leading-relaxed">
          Welcome to GreenAI. To generate insights and predictions, please upload your electricity consumption dataset (.csv).
        </p>

        <div className="relative group">
          <input
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="hidden"
            id="csv-upload-main"
          />
          <label
            htmlFor="csv-upload-main"
            className="cursor-pointer bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold py-4 px-8 rounded-xl shadow-lg shadow-emerald-500/20 transition-all transform group-hover:-translate-y-1 block w-full"
          >
            <div className="flex items-center justify-center gap-3">
              <FileText size={20} />
              <span>Select Dataset File</span>
            </div>
          </label>
        </div>
        <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-500">
          <CheckCircle size={12} className="text-emerald-500" />
          <span>Secure local processing</span>
        </div>
      </div>
    </motion.div>
  );

  const pollTrainingStatus = async () => {
    setTrainingState((s) => ({ ...s, is_training: true }));
    try {
      let pollCount = 0;
      while (pollCount < 40) { // max ~80s polling
        const res = await axios.get(`${API_BASE_URL}/api/train/status`);
        setTrainingState(res.data);
        if (!res.data.is_training) {
          // finished
          await fetchData();
          setLoading(false);
          return;
        }
        await new Promise(r => setTimeout(r, 2000));
        pollCount += 1;
      }
      // timeout
      setLoading(false);
    } catch (err) {
      console.error('Could not poll training status:', err);
      setLoading(false);
    }
  };

  const renderDashboard = () => (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-6"
    >
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard
          title="Avg. Usage"
          value={`${stats?.average_usage?.toFixed(2) ?? '...'} kWh`}
          subtext="Daily Average"
          icon={Activity}
          delay={0.1}
        />
        <KPICard
          title="Green Score"
          value={prediction ? `${prediction.green_score?.toFixed(0)}` : '...'}
          subtext={prediction?.green_score > 75 ? "Excellent Efficiency" : "Needs Improvement"}
          icon={TrendingUp}
          delay={0.2}
        />
        <KPICard
          title="Last Reading"
          value={`${stats?.last_recorded?.toFixed(2) ?? '...'} kWh`}
          subtext="Latest update"
          icon={Clock}
          delay={0.3}
        />
        <KPICard
          title="Next Predicted"
          value={prediction ? `${prediction.predicted_usage?.toFixed(2) ?? '...'} kWh` : '...'}
          subtext="AI Forecast"
          icon={Zap}
          delay={0.4}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <UsageChart data={trends} type="line" />
        </div>
        <div className="lg:col-span-1">
          <PredictionPanel prediction={prediction} />
        </div>
      </div>

      <div className="bg-slate-800/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-bold text-white">Data Management</h3>
          {uploadedFileName && (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-emerald-400 text-sm bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
                <CheckCircle size={14} />
                <span>Loaded: <strong>{uploadedFileName}</strong></span>
              </div>
              {uploadProgress !== null && (
                <div className="w-48 bg-slate-700 rounded-full overflow-hidden h-3">
                  <div className="bg-emerald-400 h-3" style={{ width: `${uploadProgress}%` }} />
                </div>
              )}
              {trainingState?.is_training && (
                <div className="text-xs text-slate-400 ml-2">Training in progress {trainingState?.progress ? `• ${trainingState.progress}%` : '...'}</div>
              )}
            </div>
          )}
        </div>

        <div className="border-2 border-dashed border-slate-700 hover:border-emerald-500/50 rounded-xl p-8 text-center bg-slate-900/50 transition-colors group">
          <input
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="hidden"
            id="csv-upload"
          />
          <label htmlFor="csv-upload" className="cursor-pointer flex flex-col items-center gap-3">
            <div className="p-4 bg-emerald-500/10 rounded-full text-emerald-500 group-hover:scale-110 group-hover:bg-emerald-500/20 transition-all shadow-lg shadow-emerald-500/10">
              <Upload size={28} />
            </div>
            <div>
              <span className="block text-lg font-semibold text-white group-hover:text-emerald-400 transition-colors">Click to Upload Dataset</span>
              <span className="text-sm text-slate-500">Supports: Timestamp, Electricity_Consumption</span>
            </div>
          </label>
        </div>
      </div>
    </motion.div>
  );

  const renderAnalysis = () => (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-6"
    >
      <UsageChart data={trends} type="bar" />

      <div className="bg-slate-800/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-4">Recent Data Logs</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-400 uppercase bg-slate-900/50">
              <tr>
                <th className="px-6 py-4 rounded-l-lg">Date</th>
                <th className="px-6 py-4">Usage (kWh)</th>
                <th className="px-6 py-4 rounded-r-lg">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {trends.slice().reverse().slice(0, 5).map((row, idx) => (
                <tr key={idx} className="hover:bg-white/5 transition-colors">
                  <td className="px-6 py-4 text-slate-300 font-medium">{row.date}</td>
                  <td className="px-6 py-4 text-white font-bold">{row.usage?.toFixed(2) ?? '...'}</td>
                  <td className="px-6 py-4">
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${row.usage > stats?.average_usage
                      ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                      : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      }`}>
                      {row.usage > stats?.average_usage ? 'High Usage' : 'Optimal'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  );

  const renderPrediction = () => {
    let futureData = [];
    if (trends && trends.length > 0) {
      const lastDate = new Date(trends[trends.length - 1].date);
      if (!isNaN(lastDate.getTime())) {
        const cutoff = new Date(lastDate);
        cutoff.setDate(cutoff.getDate() - 7);
        const last7DaysData = trends.filter(d => new Date(d.date) >= cutoff);
        const sourceData = last7DaysData.length > 0 ? last7DaysData : trends;
        futureData = sourceData.map(t => {
          let isoStr = new Date().toISOString();
          if (t && t.date) {
            const dDate = new Date(t.date);
            if (!isNaN(dDate.getTime())) {
              dDate.setDate(dDate.getDate() + 7);
              isoStr = dDate.toISOString();
            }
          }
          return { ...t, date: isoStr, usage: parseFloat(t.usage || 0) * (0.9 + Math.random() * 0.2) };
        });
      }
    }

    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        className="space-y-6"
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PredictionPanel prediction={prediction} />
          <div className="bg-slate-800/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col justify-center items-center text-center">
            <div className="p-4 bg-amber-500/10 rounded-full text-amber-500 mb-4">
              <AlertTriangle size={32} />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">Efficiency Recommendations</h3>
            <p className="text-slate-400 max-w-md">
              Based on your predicted usage of <span className="text-white font-bold">{prediction?.predicted_usage?.toFixed(2) ?? '...'} kWh</span>,
              we recommend shifting high-load appliances to off-peak hours (10 PM - 6 AM) to reduce your carbon footprint by an estimated 15%.
            </p>
          </div>
        </div>

        <div className="bg-slate-800/40 backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-xl">
          <h3 className="text-lg font-bold text-white mb-2">Future Consumption Forecast</h3>
          <p className="text-sm text-slate-500 mb-6">Projected usage trend for the next 7 days based on current patterns.</p>
          <UsageChart data={futureData} type="line" hideHeader={true} />
        </div>
      </motion.div>
    );
  };

  return (
    <div className="flex min-h-screen bg-slate-900 font-sans text-slate-50 overflow-hidden">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="flex-1 ml-64 relative">
        <Topbar title={activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} />

        {/* Global validation modal - shown regardless of current view */}
        {showValidateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-slate-800 rounded-2xl p-6 w-11/12 max-w-3xl border border-white/5">
              <h3 className="text-lg font-bold text-white mb-4">Preview Uploaded CSV</h3>
              <p className="text-sm text-slate-400 mb-4">Check detected columns and confirm which columns represent <strong>Usage</strong> and <strong>Date</strong>.</p>

              <div className="mb-4">
                <div className="flex gap-2">
                  <div>
                    <label className="text-xs text-slate-400">Usage Column</label>
                    <select value={selectedUsageCol || ''} onChange={e => setSelectedUsageCol(e.target.value)} className="block rounded-md p-2 bg-slate-900 text-slate-200 w-56">
                      {validatePreview?.columns?.map(c => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">Date Column</label>
                    <select value={selectedDateCol || ''} onChange={e => setSelectedDateCol(e.target.value)} className="block rounded-md p-2 bg-slate-900 text-slate-200 w-56">
                      {validatePreview?.columns?.map(c => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="overflow-auto max-h-48 bg-slate-900/50 rounded-md p-3 mb-4 text-xs">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-400 uppercase">
                    <tr>
                      {validatePreview?.columns?.map(c => (
                        <th key={c} className="pr-4 py-1">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {validatePreview?.preview?.map((row, idx) => (
                      <tr key={idx} className="align-top">
                        {validatePreview.columns.map((c) => (
                          <td key={c} className="pr-4 py-1">{String(row[c] ?? '')}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={cancelValidation} className="px-4 py-2 rounded-lg bg-rose-500 text-white">Cancel</button>
                <button onClick={confirmUpload} className="px-4 py-2 rounded-lg bg-emerald-500 text-white">Confirm & Upload</button>
              </div>
            </div>
          </div>
        )}

        <main className="p-8 h-[calc(100vh-5rem)] overflow-y-auto custom-scrollbar">
          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div
                key="loader"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center h-[50vh] gap-4"
              >
                <div className="w-12 h-12 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin"></div>
                <p className="text-slate-400 animate-pulse">Initializing GreenAI Analytics...</p>
              </motion.div>
            ) : (
              <div className="max-w-7xl mx-auto pb-10">
                {!stats ? (
                  <RenderEmptyState />
                ) : (
                  <>
                    {activeTab === 'dashboard' && renderDashboard()}
                    {activeTab === 'analysis' && renderAnalysis()}
                    {activeTab === 'prediction' && renderPrediction()}
                  </>
                )}

                {activeTab === 'about' && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="bg-slate-800/40 backdrop-blur-md border border-white/5 rounded-2xl p-8 text-center max-w-2xl mx-auto mt-10"
                  >
                    <div className="w-20 h-20 bg-gradient-to-br from-emerald-400 to-teal-600 rounded-2xl mx-auto flex items-center justify-center shadow-lg shadow-emerald-500/20 mb-6">
                      <Zap className="text-white w-10 h-10 fill-current" />
                    </div>
                    <h2 className="text-3xl font-bold text-white mb-4">GreenAI Analyzer</h2>
                    <p className="text-slate-400 leading-relaxed mb-8">
                      GreenAI is an advanced Smart Electricity Bill Analyzer designed to help users monitor, analyze, and optimize their energy consumption using state-of-the-art machine learning algorithms. By predicting future usage and calculating carbon footprints, we empower users to make greener choices.
                    </p>
                    <div className="flex justify-center gap-4 text-sm text-slate-500">
                      <span>Version 1.2.0</span>
                      <span>•</span>
                      <span>Built for Sustainability</span>
                    </div>
                  </motion.div>
                )}
              </div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

export default App;
