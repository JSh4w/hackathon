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
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Form state
  const [fromLocation, setFromLocation] = useState('PAD');
  const [toLocation, setToLocation] = useState('HAV');
  const [fromTime, setFromTime] = useState('0700');
  const [toTime, setToTime] = useState('1900');
  const [days, setDays] = useState('WEEKDAY');
  const [lookback, setLookback] = useState('1M'); // 1W, 1M, 2M, 3M

  // Calculate date range based on selected lookback window
  const getDateRangeForLookback = () => {
    const now = new Date();
    const end = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
    let start = new Date(end);
    if (lookback === '1W') {
      start.setUTCDate(start.getUTCDate() - 7);
    } else if (lookback === '1M') {
      start.setUTCMonth(start.getUTCMonth() - 1);
    } else if (lookback === '2M') {
      start.setUTCMonth(start.getUTCMonth() - 2);
    } else if (lookback === '3M') {
      start.setUTCMonth(start.getUTCMonth() - 3);
    }
    const fromDate = start.toISOString().split('T')[0];
    const toDate = end.toISOString().split('T')[0];
    return { fromDate, toDate };
  };

  const fetchJourneyAnalysis = async () => {
    setLoading(true);
    setError(null);
    setAiAnalysis(null);

    try {
      const { fromDate, toDate } = getDateRangeForLookback();

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

      // Scroll to results after data is loaded
      setTimeout(() => {
        const resultsSection = document.querySelector('.results-section');
        if (resultsSection) {
          resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
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

      // Scroll to results after data is loaded
      setTimeout(() => {
        const resultsSection = document.querySelector('.results-section');
        if (resultsSection) {
          resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
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

      // Scroll to results after data is loaded
      setTimeout(() => {
        const resultsSection = document.querySelector('.results-section');
        if (resultsSection) {
          resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
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

  // Derive dynamic origin/destination labels from returned route (fallback to form CRS)
  const getStationsFromRoute = (routeText) => {
    if (!routeText || typeof routeText !== 'string') {
      return [fromLocation, toLocation];
    }
    // Try common separators: "→", "-", "to", "–", "—"
    const separators = [
      /\s*→\s*/,
      /\s*-\s*/,
      /\s*–\s*/,
      /\s*—\s*/,
      /\s+to\s+/i,
      /\s*>\s*/
    ];
    for (const sep of separators) {
      const parts = routeText.split(sep);
      if (parts.length === 2) {
        const origin = (parts[0] || '').trim() || fromLocation;
        const destination = (parts[1] || '').trim() || toLocation;
        return [origin, destination];
      }
    }
    return [fromLocation, toLocation];
  };

  const [originLabel, destinationLabel] = getStationsFromRoute(
    histogramData?.route || `${fromLocation} → ${toLocation}`
  );

  return (
    <div className="app-container">
      {/* Main Content */}
      <div className="main-content">
        <div className="content-center">
          {/* Brand Logo */}
          <div className="main-brand">
            <h1>trelay</h1>
          </div>

          {/* Main Interface - Three Dot Dropdown */}
          <div className="main-interface">
            <div className="interface-header">
              <h2>Journey Analysis Settings</h2>
              <button
                className="dropdown-toggle"
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                <svg viewBox="0 0 24 24" width="24" height="24">
                  <path fill="currentColor" d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/>
                </svg>
              </button>
            </div>

            {/* Advanced Options - Now Main Interface */}
            {showAdvanced && (
              <div className="advanced-options">
                <div className="form-grid">
                  <div className="form-field">
                    <label>From</label>
                    <input
                      type="text"
                      value={fromLocation}
                      onChange={(e) => setFromLocation(e.target.value.toUpperCase())}
                      placeholder="PAD"
                      maxLength="3"
                    />
                  </div>
                  <div className="form-field">
                    <label>To</label>
                    <input
                      type="text"
                      value={toLocation}
                      onChange={(e) => setToLocation(e.target.value.toUpperCase())}
                      placeholder="HAV"
                      maxLength="3"
                    />
                  </div>
                  <div className="form-field">
                    <label>From Time</label>
                    <input
                      type="time"
                      value={fromTime.slice(0, 2) + ':' + fromTime.slice(2)}
                      onChange={(e) => setFromTime(e.target.value.replace(':', ''))}
                    />
                  </div>
                  <div className="form-field">
                    <label>To Time</label>
                    <input
                      type="time"
                      value={toTime.slice(0, 2) + ':' + toTime.slice(2)}
                      onChange={(e) => setToTime(e.target.value.replace(':', ''))}
                    />
                  </div>
                  <div className="form-field">
                    <label>Days</label>
                    <select value={days} onChange={(e) => setDays(e.target.value)}>
                      <option value="WEEKDAY">Weekdays</option>
                      <option value="SATURDAY">Saturdays</option>
                      <option value="SUNDAY">Sundays</option>
                    </select>
                  </div>
                  <div className="form-field">
                    <label>Lookback</label>
                    <select value={lookback} onChange={(e) => setLookback(e.target.value)}>
                      <option value="1W">1 week</option>
                      <option value="1M">1 month</option>
                      <option value="2M">2 months</option>
                      <option value="3M">3 months</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="action-buttons">
            <button
              onClick={fetchJourneyAnalysis}
              disabled={loading || aiLoading}
              className="action-btn performance"
            >
              <svg viewBox="0 0 24 24" width="20" height="20">
                <path fill="currentColor" d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/>
              </svg>
              {loading ? 'Analyzing...' : 'Analyze'}
            </button>

            <button
              onClick={fetchHistogramData}
              disabled={loading || aiLoading}
              className="action-btn demo"
            >
              <svg viewBox="0 0 24 24" width="20" height="20">
                <path fill="currentColor" d="M9,4V6H14V4H16V6H17A1,1 0 0,1 18,7V19A1,1 0 0,1 17,20H7A1,1 0 0,1 6,19V7A1,1 0 0,1 7,6H8V4H9M7,8V19H17V8H7Z"/>
              </svg>
              {loading ? 'Loading...' : 'Demo'}
            </button>

            <button
              onClick={fetchAiAnalysis}
              disabled={loading || aiLoading}
              className="action-btn ai"
            >
              <svg viewBox="0 0 24 24" width="20" height="20">
                <path fill="currentColor" d="M12,2A2,2 0 0,1 14,4C14,4.74 13.6,5.39 13,5.73V7H14A7,7 0 0,1 21,14H22A1,1 0 0,1 23,15V18A1,1 0 0,1 22,19H21V20A2,2 0 0,1 19,22H5A2,2 0 0,1 3,20V19H2A1,1 0 0,1 1,18V15A1,1 0 0,1 2,14H3A7,7 0 0,1 10,7H11V5.73C10.4,5.39 10,4.74 10,4A2,2 0 0,1 12,2M7.5,13A2.5,2.5 0 0,0 5,15.5A2.5,2.5 0 0,0 7.5,18A2.5,2.5 0 0,0 10,15.5A2.5,2.5 0 0,0 7.5,13M16.5,13A2.5,2.5 0 0,0 14,15.5A2.5,2.5 0 0,0 16.5,18A2.5,2.5 0 0,0 19,15.5A2.5,2.5 0 0,0 16.5,13Z"/>
              </svg>
              {aiLoading ? 'Processing...' : 'AI Analysis'}
            </button>
          </div>

          {/* Error Display */}
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          {/* Results Section */}
          {histogramData && (
            <div className="results-section">
              {aiAnalysis && (
                <div className="ai-analysis">
                  <h2>AI Travel Analysis</h2>
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
                <div className="timeline-header">
                  <div className="timeline-station departure-station">
                    <div className="station-icon">🚉</div>
                    <h3>{originLabel}</h3>
                    <p>Departure Performance</p>
                  </div>

                  <div className="timeline-journey">
                    <div className="journey-track"></div>
                    <div className="journey-train">🚊</div>
                    <div className="journey-label">Journey Time</div>
                  </div>

                  <div className="timeline-station arrival-station">
                    <div className="station-icon">🏁</div>
                    <h3>{destinationLabel}</h3>
                    <p>Arrival Performance</p>
                  </div>
                </div>

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
                              tooltip: {
                                callbacks: {
                                  label: function(context) {
                                    const rawVal = typeof context.parsed === 'object' ? context.parsed.y : context.parsed;
                                    const value = typeof rawVal === 'number' ? rawVal : 0;
                                    return `${value}%`;
                                  }
                                }
                              }
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
                              tooltip: {
                                callbacks: {
                                  label: function(context) {
                                    const rawVal = typeof context.parsed === 'object' ? context.parsed.y : context.parsed;
                                    const value = typeof rawVal === 'number' ? rawVal : 0;
                                    return `${value}%`;
                                  }
                                }
                              }
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
        </div>
      </div>
    </div>
  );
}

export default App;