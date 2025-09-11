import React, { useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import './App.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

function App() {
  const [histogramData, setHistogramData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  
  // Form state
  const [fromLocation, setFromLocation] = useState('PAD');
  const [toLocation, setToLocation] = useState('HAV');
  const [fromTime, setFromTime] = useState('0700');
  const [toTime, setToTime] = useState('1900');
  const [days, setDays] = useState('WEEKDAY');

  // Calculate last month date range
  const getLastMonthDateRange = () => {
    const now = new Date();
    const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const endOfLastMonth = new Date(now.getFullYear(), now.getMonth(), 0);
    
    return {
      fromDate: lastMonth.toISOString().split('T')[0],
      toDate: endOfLastMonth.toISOString().split('T')[0]
    };
  };

  const fetchJourneyAnalysis = async () => {
    setLoading(true);
    setError(null);
    setAiAnalysis(null);
    
    try {
      const { fromDate, toDate } = getLastMonthDateRange();
      
      const requestBody = {
        from_loc: fromLocation,
        to_loc: toLocation,
        from_time: fromTime,
        to_time: toTime,
        from_date: fromDate,
        to_date: toDate,
        days: days
      };
      
      const response = await fetch('http://localhost:8000/api/v1/journey-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setHistogramData(data);
    } catch (err) {
      setError(`Failed to fetch data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistogramData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/v1/delays/histogram');
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setHistogramData(data);
    } catch (err) {
      setError(`Failed to fetch data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchAiAnalysis = async () => {
    setAiLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/v1/ai-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setHistogramData(data.histogram_data);
      setAiAnalysis(data.ai_analysis);
    } catch (err) {
      setError(`Failed to fetch AI analysis: ${err.message}`);
    } finally {
      setAiLoading(false);
    }
  };

  const createChartData = (delayData, title, color) => {
    if (!delayData || !delayData.histogram) return null;

    const labels = Object.keys(delayData.histogram);
    const values = Object.values(delayData.histogram);

    return {
      labels,
      datasets: [
        {
          label: `${title} (Services)`,
          data: values,
          backgroundColor: color,
          borderColor: color.replace('0.6', '1'),
          borderWidth: 1,
        },
      ],
    };
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Delay (minutes)'
        }
      },
      y: {
        title: {
          display: true,
          text: 'Number of Services'
        },
        beginAtZero: true,
      },
    },
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="brand-header">
          <div className="brand-logo">
            <span className="brand-main">Trelay</span>
            <span className="brand-sub">Train Delay Intelligence</span>
          </div>
          <p className="route-info">Analyze Railway Performance for Any Journey</p>
        </div>

        <div className="journey-form">
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="fromLocation">From</label>
              <input
                type="text"
                id="fromLocation"
                value={fromLocation}
                onChange={(e) => setFromLocation(e.target.value.toUpperCase())}
                placeholder="e.g., PAD, EUS, KGX"
                maxLength="3"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="toLocation">To</label>
              <input
                type="text"
                id="toLocation"
                value={toLocation}
                onChange={(e) => setToLocation(e.target.value.toUpperCase())}
                placeholder="e.g., HAV, OXF, BRI"
                maxLength="3"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="fromTime">From Time</label>
              <input
                type="time"
                id="fromTime"
                value={fromTime.slice(0, 2) + ':' + fromTime.slice(2)}
                onChange={(e) => setFromTime(e.target.value.replace(':', ''))}
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="toTime">To Time</label>
              <input
                type="time"
                id="toTime"
                value={toTime.slice(0, 2) + ':' + toTime.slice(2)}
                onChange={(e) => setToTime(e.target.value.replace(':', ''))}
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="days">Days</label>
              <select
                id="days"
                value={days}
                onChange={(e) => setDays(e.target.value)}
              >
                <option value="WEEKDAY">Weekdays</option>
                <option value="SATURDAY">Saturdays</option>
                <option value="SUNDAY">Sundays</option>
              </select>
            </div>
          </div>

          <div className="analysis-info">
            <p>🗓️ Analysis covers the last month of data</p>
          </div>
        </div>
        
        <div className="button-container">
          <button 
            onClick={fetchJourneyAnalysis} 
            disabled={loading || aiLoading}
            className="fetch-button primary-button"
          >
            {loading ? 'Analyzing Journey...' : '📊 Analyze Journey Performance'}
          </button>
          
          <button 
            onClick={fetchHistogramData} 
            disabled={loading || aiLoading}
            className="fetch-button secondary-button"
          >
            {loading ? 'Loading...' : 'Show Demo Data (PAD→HAV)'}
          </button>
        </div>

        {error && (
          <div className="error">
            {error}
          </div>
        )}

        {histogramData && (
          <div className="histogram-container">
            {aiAnalysis && (
              <div className="ai-analysis">
                <h2>🤖 AI Travel Analysis</h2>
                <div className="ai-content">
                  {aiAnalysis.split('\n').map((line, index) => (
                    <p key={index}>{line}</p>
                  ))}
                </div>
              </div>
            )}
            
            <div className="summary">
              <h2>Summary Statistics</h2>
              <div className="stats-grid">
                <div className="stat-card">
                  <h3>Route</h3>
                  <p>{histogramData.route}</p>
                </div>
                <div className="stat-card">
                  <h3>Date Range</h3>
                  <p>{histogramData.date_range || 'Historical Data'}</p>
                </div>
                <div className="stat-card">
                  <h3>Time Window</h3>
                  <p>{histogramData.time_range || '07:00 - 19:00'}</p>
                </div>
                <div className="stat-card">
                  <h3>Days</h3>
                  <p>{histogramData.days || 'Weekdays'}</p>
                </div>
                <div className="stat-card">
                  <h3>Total Services</h3>
                  <p>{histogramData.total_services}</p>
                </div>
                <div className="stat-card">
                  <h3>Analyzed Services</h3>
                  <p>{histogramData.analyzed_services}</p>
                </div>
              </div>
            </div>

            <div className="timeline-container">
              {/* Timeline Header */}
              <div className="timeline-header">
                <div className="timeline-station departure-station">
                  <div className="station-icon">🚉</div>
                  <h3>Paddington</h3>
                  <p>Departure Performance</p>
                </div>
                
                <div className="timeline-journey">
                  <div className="journey-track"></div>
                  <div className="journey-train">🚊</div>
                  <div className="journey-label">Journey Time</div>
                </div>
                
                <div className="timeline-station arrival-station">
                  <div className="station-icon">🏁</div>
                  <h3>Havant</h3>
                  <p>Arrival Performance</p>
                </div>
              </div>

              {/* Seamless Charts Timeline */}
              <div className="timeline-charts">
                <div className="timeline-segment departure-segment">
                  <div className="segment-stats">
                    <div className="stat-badge">
                      <span className="stat-value">{histogramData.departure_delays.avg_delay.toFixed(1)}min</span>
                      <span className="stat-label">Avg Delay</span>
                    </div>
                    <div className="stat-badge">
                      <span className="stat-value">{Math.round((histogramData.departure_delays.on_time_count / histogramData.analyzed_services) * 100)}%</span>
                      <span className="stat-label">On Time</span>
                    </div>
                    {histogramData.departure_delays.extreme_delays > 0 && (
                      <div className="stat-badge extreme-badge">
                        <span className="stat-value">{histogramData.departure_delays.extreme_delays}</span>
                        <span className="stat-label">Extreme Delays (>30min)</span>
                      </div>
                    )}
                  </div>
                  
                  {createChartData(histogramData.departure_delays, 'Departures', 'rgba(97, 218, 251, 0.8)') && (
                    <div className="chart-wrapper">
                      <Bar 
                        data={createChartData(histogramData.departure_delays, 'Departures', 'rgba(97, 218, 251, 0.8)')} 
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: { display: false },
                            title: { display: false },
                          },
                          scales: {
                            x: {
                              display: true,
                              grid: { display: false },
                              ticks: { 
                                color: 'rgba(255,255,255,0.8)',
                                font: { size: 11 }
                              }
                            },
                            y: {
                              display: true,
                              grid: { 
                                color: 'rgba(255,255,255,0.1)',
                                borderDash: [2, 2]
                              },
                              ticks: { 
                                color: 'rgba(255,255,255,0.8)',
                                font: { size: 11 }
                              },
                              beginAtZero: true,
                            },
                          },
                          elements: {
                            bar: {
                              borderRadius: 4,
                              borderSkipped: false,
                            }
                          }
                        }} 
                      />
                    </div>
                  )}
                </div>

                <div className="timeline-connector">
                  <div className="connector-line"></div>
                  <div className="connector-train">
                    <svg viewBox="0 0 60 30" className="mini-train">
                      <rect x="10" y="8" width="40" height="14" fill="rgba(97, 218, 251, 0.9)" rx="2"/>
                      <circle cx="18" cy="24" r="3" fill="#444"/>
                      <circle cx="42" cy="24" r="3" fill="#444"/>
                      <rect x="14" y="11" width="4" height="4" fill="rgba(255,255,255,0.8)" rx="1"/>
                      <rect x="20" y="11" width="4" height="4" fill="rgba(255,255,255,0.8)" rx="1"/>
                      <rect x="26" y="11" width="4" height="4" fill="rgba(255,255,255,0.8)" rx="1"/>
                      <rect x="32" y="11" width="4" height="4" fill="rgba(255,255,255,0.8)" rx="1"/>
                    </svg>
                  </div>
                  <div className="connector-time">
                    <span>~{Math.round((histogramData.departure_delays.avg_delay + histogramData.arrival_delays.avg_delay) / 2 + 45)}min</span>
                  </div>
                </div>

                <div className="timeline-segment arrival-segment">
                  <div className="segment-stats">
                    <div className="stat-badge">
                      <span className="stat-value">{histogramData.arrival_delays.avg_delay.toFixed(1)}min</span>
                      <span className="stat-label">Avg Delay</span>
                    </div>
                    <div className="stat-badge">
                      <span className="stat-value">{Math.round((histogramData.arrival_delays.on_time_count / histogramData.analyzed_services) * 100)}%</span>
                      <span className="stat-label">On Time</span>
                    </div>
                    {histogramData.arrival_delays.extreme_delays > 0 && (
                      <div className="stat-badge extreme-badge">
                        <span className="stat-value">{histogramData.arrival_delays.extreme_delays}</span>
                        <span className="stat-label">Extreme Delays (>30min)</span>
                      </div>
                    )}
                  </div>
                  
                  {createChartData(histogramData.arrival_delays, 'Arrivals', 'rgba(255, 107, 107, 0.8)') && (
                    <div className="chart-wrapper">
                      <Bar 
                        data={createChartData(histogramData.arrival_delays, 'Arrivals', 'rgba(255, 107, 107, 0.8)')} 
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: { display: false },
                            title: { display: false },
                          },
                          scales: {
                            x: {
                              display: true,
                              grid: { display: false },
                              ticks: { 
                                color: 'rgba(255,255,255,0.8)',
                                font: { size: 11 }
                              }
                            },
                            y: {
                              display: true,
                              grid: { 
                                color: 'rgba(255,255,255,0.1)',
                                borderDash: [2, 2]
                              },
                              ticks: { 
                                color: 'rgba(255,255,255,0.8)',
                                font: { size: 11 }
                              },
                              beginAtZero: true,
                            },
                          },
                          elements: {
                            bar: {
                              borderRadius: 4,
                              borderSkipped: false,
                            }
                          }
                        }} 
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </header>
    </div>
  );
}

export default App;