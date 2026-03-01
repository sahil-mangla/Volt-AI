

import { useState, useEffect } from 'react'
import { Activity, AlertTriangle, CheckCircle, BarChart3, Settings, Database } from 'lucide-react'
import voltaiLogo from './assets/voltai-logo.svg'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function Dashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  // Settings State with Persistence
  const [settings, setSettings] = useState(() => {
    const saved = localStorage.getItem('volt_settings');
    return saved ? JSON.parse(saved) : {
      criticalThreshold: 70,
      warningThreshold: 80,
      refreshRate: '5 Seconds',
      model: 'XGBoost (Production)'
    };
  });

  const [fleetData, setFleetData] = useState([]);
  const [selectedBattery, setSelectedBattery] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showWorkOrderModal, setShowWorkOrderModal] = useState(false);
  const [notification, setNotification] = useState({ visible: false, message: '', type: '' });

  const saveSettings = () => {
    localStorage.setItem('volt_settings', JSON.stringify(settings));
    
    setNotification({
      visible: true,
      message: 'Configuration saved successfully!',
      type: 'success'
    });

    setTimeout(() => {
      setNotification(prev => ({ ...prev, visible: false }));
    }, 3000);
  };

  // Fetch Fleet Summary & Apply Settings
  useEffect(() => {
    // Determine model query param based on settings
    const baseUrl = import.meta.env.VITE_API_URL || '/api';
    const modelParam = settings.model.includes('LSTM') ? 'lstm' : 'linear';
    
    fetch(`${baseUrl}/batteries?model_type=${modelParam}`)
      .then(res => res.json())
      .then(data => {
        // Apply dynamic thresholds
        const processedData = data.map(b => {
          let status = 'HEALTHY';
          // Keep existing status logic or backend logic
          if (b.health < settings.criticalThreshold) status = 'CRITICAL';
          else if (b.health < settings.warningThreshold) status = 'WARNING';
          
          // If maintenance, keep it (unless we want to overwrite it with health status)
          // For now, let's respect the local override if we had one, but effectively we are overwriting 
          // fleetData every time. 
          // Ideally we should merge with existing state to preserve "MAINTENANCE" status if it's local only.
          // But for this prototype, simple refresh is fine.
          
          return { ...b, status };
        });

        setFleetData(processedData);
        if (processedData.length > 0 && !selectedBattery) {
          setSelectedBattery(processedData[0].id); 
        }
        setLoading(false);
      })
      .catch(err => console.error("Failed to fetch fleet data:", err));
  }, [settings]); // Re-run when settings change

  // Fetch History for Selected Battery
  useEffect(() => {
    if (selectedBattery) {
      const modelParam = settings.model.includes('LSTM') ? 'lstm' : 'linear';
      const baseUrl = import.meta.env.VITE_API_URL || '/api';
    fetch(`${baseUrl}/batteries/${selectedBattery}?model_type=${modelParam}`)
        .then(res => res.json())
        .then(data => {
          if (data && data.history) {
            setHistoryData(data.history);
          }
        })
        .catch(err => console.error("Failed to fetch history:", err));
    }
  }, [selectedBattery, settings.model]);

  const getAvgHealth = () => {
    if (!fleetData.length) return 0;
    return Math.round(fleetData.reduce((acc, b) => acc + b.health, 0) / fleetData.length);
  };

  const getCriticalCount = () => {
    return fleetData.filter(b => b.status === 'CRITICAL').length;
  };

  const handleNavClick = (tab) => {
    setActiveTab(tab);
    setSidebarOpen(false);
  };

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">

      {/* Mobile overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar / Navigation */}
      <nav className={`fixed top-0 left-0 h-full w-64 border-r border-border bg-card p-4 z-40 transition-transform duration-300
        ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0`}>
        <div className="flex items-center gap-2 mb-8">
          <img src={voltaiLogo} alt="VoltAI" className="h-8 w-8" />
          <h1 className="text-xl font-bold">VoltAI Platform</h1>
        </div>
        
        <div className="space-y-2">
          <NavItem icon={<BarChart3 />} label="Overview" active={activeTab === 'overview'} onClick={() => handleNavClick('overview')} />
          <NavItem icon={<Activity />} label="Live Telemetry" active={activeTab === 'telemetry'} onClick={() => handleNavClick('telemetry')} />
          <NavItem icon={<Database />} label="Fleet Data" active={activeTab === 'data'} onClick={() => handleNavClick('data')} />
          <NavItem icon={<Settings />} label="Settings" active={activeTab === 'settings'} onClick={() => handleNavClick('settings')} />
        </div>
      </nav>

      {/* Mobile Top Bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-card border-b border-border flex items-center px-4 gap-3 z-20">
        <button
          onClick={() => setSidebarOpen(true)}
          className="p-2 rounded-lg hover:bg-secondary transition-colors"
          aria-label="Open menu"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <img src={voltaiLogo} alt="VoltAI" className="h-7 w-7" />
        <span className="font-bold text-base">VoltAI Platform</span>
      </div>

      {/* Main Content */}
      <main className="md:ml-64 pt-14 md:pt-0 p-4 md:p-8">
        <header className="mb-6 md:mb-8">
          <div className="mb-4">
            <h2 className="text-2xl md:text-3xl font-bold">
              {activeTab === 'overview' && 'Fleet Dashboard'}
              {activeTab === 'telemetry' && 'Live Telemetry'}
              {activeTab === 'data' && 'Fleet Data Explorer'}
              {activeTab === 'settings' && 'System Settings'}
            </h2>
            <p className="text-muted-foreground text-sm md:text-base">
              {activeTab === 'overview' && `Real-time predictive intelligence for ${fleetData.length} active units.`}
              {activeTab === 'telemetry' && 'Monitoring real-time voltage, current, and temperature streams.'}
              {activeTab === 'data' && 'Deep dive into historical charge cycles and degradation patterns.'}
              {activeTab === 'settings' && 'Configure alert thresholds and model parameters.'}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <StatCard label="Avg Fleet Health" value={`${getAvgHealth()}%`} status={getAvgHealth() < settings.warningThreshold ? 'warning' : 'normal'} />
            <StatCard label="Predicted Failures" value={getCriticalCount()} status={getCriticalCount() > 0 ? 'critical' : 'normal'} />
          </div>
        </header>

        {/* Dynamic Content */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
            
            {/* Main Chart - Health Trend */}
            <div className="lg:col-span-2 bg-card border border-border rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">
                Degradation Trend: <span className="text-primary">{selectedBattery || 'Loading...'}</span>
              </h3>
              <div className="h-[300px] w-full">
                {historyData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={historyData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis dataKey="cycle" stroke="#888" label={{ value: 'Cycle', position: 'insideBottom', offset: -5 }} />
                      <YAxis stroke="#888" domain={['auto', 'auto']} />
                      <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} />
                      <Legend />
                      <Line type="monotone" dataKey="health_score" stroke="#3b82f6" strokeWidth={2} name="Health Score (%)" dot={false} />
                      {/* RUL might be too large for this axis, so maybe visualize differently or dual axis. For now let's just show health. */}
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground">
                    {loading ? "Loading data..." : "Select a battery to view history"}
                  </div>
                )}
              </div>
            </div>

            {/* Fleet Status List */}
            <div className="bg-card border border-border rounded-xl p-6 overflow-y-auto max-h-[400px]">
              <h3 className="text-lg font-semibold mb-4">Fleet Status</h3>
              <div className="space-y-4">
                {fleetData.map((battery) => (
                  <div 
                    key={battery.id} 
                    onClick={() => setSelectedBattery(battery.id)}
                    className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                      selectedBattery === battery.id ? 'bg-primary/20 border border-primary/50' : 'bg-secondary/50 hover:bg-secondary'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <StatusIcon status={battery.status} />
                      <div>
                        <p className="font-medium">{battery.id}</p>
                        <p className="text-xs text-muted-foreground">RUL: {battery.rul} cycles</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`font-bold ${getStatusColor(battery.status)}`}>{battery.health}%</p>
                      <p className="text-xs text-muted-foreground">Health</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Critical Alerts */}
            {getCriticalCount() > 0 && (
              <div className="lg:col-span-3 bg-destructive/10 border border-destructive/20 rounded-xl p-6">
                <div className="flex items-start gap-4">
                  <AlertTriangle className="h-6 w-6 text-destructive mt-1" />
                  <div>
                    <h3 className="text-lg font-semibold text-destructive mb-1">Critical Reliability Alert</h3>
                    <p className="text-muted-foreground">
                      {getCriticalCount()} unit(s) have dropped below the safety threshold.
                      Immediate maintenance required.
                    </p>
                  </div>
                  <button 
                    onClick={() => setShowWorkOrderModal(true)}
                    className="ml-auto bg-destructive text-destructive-foreground px-4 py-2 rounded-lg hover:bg-destructive/90 transition-colors"
                  >
                    Open Work Order
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Work Order Modal */}
        {showWorkOrderModal && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-card border border-border rounded-xl p-6 w-full max-w-md shadow-2xl">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                  Create Work Order
                </h3>
                <button onClick={() => setShowWorkOrderModal(false)} className="text-muted-foreground hover:text-foreground">✕</button>
              </div>
              
              <div className="space-y-4 mb-6">
                <div className="bg-secondary/30 p-4 rounded-lg">
                  <p className="text-sm font-medium mb-2">Affected Units:</p>
                  <ul className="space-y-1">
                    {fleetData.filter(b => b.status === 'CRITICAL').map(b => (
                      <li key={b.id} className="text-sm flex justify-between">
                        <span>{b.id}</span>
                        <span className="text-destructive font-bold">{b.health}% Health</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Priority Level</label>
                  <select className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm">
                    <option>High - Immediate Dispatch</option>
                    <option>Medium - Schedule within 24h</option>
                    <option>Low - Next Maintenance Cycle</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Maintenance Notes</label>
                  <textarea 
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm min-h-[80px]"
                    placeholder="Describe the issue..."
                    defaultValue={`Automatic alert: ${getCriticalCount()} unit(s) below critical threshold.`}
                  ></textarea>
                </div>
              </div>

              <div className="flex gap-3">
                <button 
                  onClick={() => setShowWorkOrderModal(false)}
                  className="flex-1 px-4 py-2 border border-border rounded-lg hover:bg-secondary transition-colors"
                >
                  Cancel
                </button>
                <button 
                  onClick={() => {
                    // Update local state to remove critical status
                    const updatedFleet = fleetData.map(b => 
                      b.status === 'CRITICAL' ? { ...b, status: 'MAINTENANCE' } : b
                    );
                    setFleetData(updatedFleet);
                    setShowWorkOrderModal(false);
                    
                    // Show floating notification
                    setNotification({
                      visible: true,
                      message: `Work Order #WO-${Math.floor(Math.random() * 10000)} Dispatched Successfully!`,
                      type: 'success'
                    });
                    
                    // Auto-hide notification
                    setTimeout(() => {
                      setNotification(prev => ({ ...prev, visible: false }));
                    }, 5000);
                  }}
                  className="flex-1 bg-destructive text-destructive-foreground px-4 py-2 rounded-lg hover:bg-destructive/90 transition-colors font-medium"
                >
                  Dispatch Team
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Floating Notification Toast */}
        {notification?.visible && (
          <div className="fixed bottom-8 right-8 bg-foreground text-background px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-bottom-4 duration-300 z-50">
            <CheckCircle className="h-5 w-5 text-green-500" />
            <div>
              <p className="font-bold">System Update</p>
              <p className="text-sm opacity-90">{notification.message}</p>
            </div>
          </div>
        )}

        {/* Placeholder Views for Other Tabs */}
        {activeTab === 'telemetry' && (
          <div className="bg-card border border-border rounded-xl p-12 text-center text-muted-foreground">
            <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <h3 className="text-xl font-semibold">Live Telemetry Coming Soon</h3>
            <p>Real-time socket connection to vehicle BMS will be implemented in Phase 2.</p>
          </div>
        )}

        {activeTab === 'data' && (
          <div className="bg-card border border-border rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">
              Historical Cycle Records: <span className="text-primary">{selectedBattery || 'Select a Battery'}</span>
            </h3>
            
            {historyData.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground text-sm">
                      <th className="p-3">Cycle</th>
                      <th className="p-3">Health Score</th>
                      <th className="p-3">Capacity (Ah)</th>
                      <th className="p-3">Avg Voltage (V)</th>
                      <th className="p-3">Avg Temp (°C)</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {historyData.map((row, idx) => (
                      <tr key={idx} className="border-b border-border/50 hover:bg-secondary/50 transition-colors">
                        <td className="p-3 font-medium">{row.cycle}</td>
                        <td className="p-3">
                          <span className={`px-2 py-1 rounded text-xs font-bold ${
                            row.health_score > settings.warningThreshold ? 'bg-green-500/20 text-green-500' : 
                            row.health_score > settings.criticalThreshold ? 'bg-orange-500/20 text-orange-500' : 'bg-red-500/20 text-red-500'
                          }`}>
                            {row.health_score?.toFixed(1)}%
                          </span>
                        </td>
                        <td className="p-3">{row.capacity?.toFixed(3)}</td>
                        <td className="p-3">{row.voltage_mean?.toFixed(3)}</td>
                        <td className="p-3">{row.temperature_mean?.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select a battery from the Overview tab to view its records.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Alert Thresholds Configuration */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <AlertTriangle className="h-6 w-6 text-primary" />
                <h3 className="text-lg font-semibold">Alert Thresholds</h3>
              </div>
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium mb-2">Critical Health Threshold (%)</label>
                  <p className="text-xs text-muted-foreground mb-3">Batteries below this level trigger immediate replacement orders.</p>
                  <input 
                    type="range" min="0" max="100" 
                    value={settings.criticalThreshold}
                    onChange={(e) => setSettings({...settings, criticalThreshold: parseInt(e.target.value)})}
                    className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>0%</span>
                    <span className="font-bold text-primary">{settings.criticalThreshold}%</span>
                    <span>100%</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Warning Health Threshold (%)</label>
                  <p className="text-xs text-muted-foreground mb-3">Batteries below this level are flagged for inspection.</p>
                  <input 
                    type="range" min="0" max="100" 
                    value={settings.warningThreshold}
                    onChange={(e) => setSettings({...settings, warningThreshold: parseInt(e.target.value)})}
                    className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>0%</span>
                    <span className="font-bold text-primary">{settings.warningThreshold}%</span>
                    <span>100%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* System Preferences */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <Settings className="h-6 w-6 text-primary" />
                <h3 className="text-lg font-semibold">System Preferences</h3>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
                  <div>
                    <p className="font-medium">Data Refresh Rate</p>
                    <p className="text-xs text-muted-foreground">Interval for fetching new telemetry</p>
                  </div>
                  <select 
                    value={settings.refreshRate}
                    onChange={(e) => setSettings({...settings, refreshRate: e.target.value})}
                    className="bg-background border border-border rounded px-2 py-1 text-sm"
                  >
                    <option>5 Seconds</option>
                    <option>10 Seconds</option>
                    <option>30 Seconds</option>
                    <option>1 Minute</option>
                  </select>
                </div>

                <div className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg">
                  <div>
                    <p className="font-medium">Predictive Model</p>
                    <p className="text-xs text-muted-foreground">Engine used for RUL calculation</p>
                  </div>
                  <select 
                     value={settings.model}
                     onChange={(e) => setSettings({...settings, model: e.target.value})}
                     className="bg-background border border-border rounded px-2 py-1 text-sm"
                  >
                    <option>XGBoost (Production)</option>
                    <option>LSTM (Experimental)</option>
                    <option>Linear Regression (Baseline)</option>
                  </select>
                </div>

                <div className="pt-6 mt-6 border-t border-border">
                  <button 
                    onClick={saveSettings}
                    className="w-full bg-primary text-primary-foreground py-2 rounded-lg font-medium hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20"
                  >
                    Save Configuration
                  </button>
                  <p className="text-xs text-center text-muted-foreground mt-2">
                    Last update: {new Date().toLocaleDateString()} by Admin
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

// Helper Components
function NavItem({ icon, label, active, onClick }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
        active ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary'
      }`}
    >
      {icon}
      <span className="font-medium">{label}</span>
    </button>
  )
}

function StatCard({ label, value, status }) {
  return (
    <div className="bg-card border border-border px-4 md:px-6 py-3 rounded-lg flex-1 min-w-[130px]">
      <p className="text-xs md:text-sm text-muted-foreground">{label}</p>
      <p className={`text-xl md:text-2xl font-bold ${
        status === 'critical' ? 'text-destructive' : 
        status === 'warning' ? 'text-orange-500' : 'text-foreground'
      }`}>{value}</p>
    </div>
  )
}

function StatusIcon({ status }) {
  if (status === 'CRITICAL') return <AlertTriangle className="h-5 w-5 text-destructive" />
  if (status === 'WARNING') return <AlertTriangle className="h-5 w-5 text-orange-500" />
  if (status === 'MAINTENANCE') return <Settings className="h-5 w-5 text-blue-500 animate-spin-slow" />
  return <CheckCircle className="h-5 w-5 text-green-500" />
}

function getStatusColor(status) {
  if (status === 'CRITICAL') return 'text-destructive'
  if (status === 'WARNING') return 'text-orange-500'
  if (status === 'MAINTENANCE') return 'text-blue-500'
  return 'text-green-500'
}

export default Dashboard
