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
          <p className="route-info">Paddington → Havant Route Performance</p>
        </div>
        
        <div className="button-container">
          <button 
            onClick={fetchHistogramData} 
            disabled={loading || aiLoading}
            className="fetch-button"
          >
            {loading ? 'Loading...' : 'Get Delay Histograms'}
          </button>
          
          <button 
            onClick={fetchAiAnalysis} 
            disabled={loading || aiLoading}
            className="fetch-button ai-button"
          >
            {aiLoading ? 'Analyzing with AI...' : '🤖 Get AI Analysis'}
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