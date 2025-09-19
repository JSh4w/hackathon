# 🚄 trelay

**Railway Journey Performance Analysis Platform**

trelay is a comprehensive railway data analysis tool that provides insights into train performance, delays, and reliability patterns using historical service data from the UK rail network.

## ✨ Features

### 📊 Journey Analysis
- **Real-time Performance Analysis**: Analyze departure and arrival delays for any UK rail route
- **Historical Data Access**: Query performance data from 2016 to present
- **Smart Date Selection**: Choose between recent data (lookback periods) or specific historical ranges
- **Visual Analytics**: Interactive charts showing delay distribution and performance metrics

### 🤖 AI-Powered Insights
- **Intelligent Analysis**: OpenAI-powered insights into delay patterns and travel recommendations
- **Performance Predictions**: Probability assessments for future journey delays
- **Travel Optimization**: Best time recommendations based on historical performance

### ⚡ Advanced Features
- **Caching System**: SQLite-based caching for faster subsequent queries
- **Progress Tracking**: Real-time progress indicators for long-running analyses
- **Station Code Support**: Full UK railway station code integration
- **Responsive Design**: Modern, mobile-friendly interface

## 🏗️ Architecture

### Backend (Python/FastAPI)
- **FastAPI**: High-performance API framework
- **HSP Integration**: Direct integration with Historical Service Performance API
- **SQLite Caching**: Intelligent caching system for API responses
- **OpenAI Integration**: AI-powered analysis and insights

### Frontend (React)
- **React 19**: Modern React with hooks and functional components
- **Chart.js**: Interactive data visualization
- **Responsive UI**: Clean, professional interface design
- **Real-time Updates**: Live progress tracking and status updates

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- HSP API credentials
- OpenAI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/trelay.git
   cd trelay
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   Create a `.env` file in the backend directory:
   ```env
   RAIL_EMAIL=your_hsp_email@domain.com
   RAIL_PWORD=your_hsp_password
   OPENAI_API_KEY=your_openai_api_key
   ```

4. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   ```

### Running the Application

1. **Start the Backend**
   ```bash
   cd backend
   python main.py
   ```
   Backend will be available at `http://localhost:8000`

2. **Start the Frontend**
   ```bash
   cd frontend
   npm start
   ```
   Frontend will be available at `http://localhost:3000`

## 📖 Usage

### Basic Journey Analysis
1. Select your departure and arrival stations (use 3-letter station codes)
2. Choose your time window and travel days
3. Select date range (recent data or historical)
4. Click "Analyze" to generate performance insights

### Understanding the Results
- **Departure Performance**: Shows delay distribution for departures from origin station
- **Arrival Performance**: Shows delay distribution for arrivals at destination station
- **On-Time Performance**: Percentage of services within ±1 minute of schedule
- **Reliability Score**: Overall service reliability percentage

### Station Codes
Use standard UK railway station codes (CRS codes):
- `EUS` - London Euston
- `KGL` - Kings Langley
- `BTN` - Brighton
- `VIC` - London Victoria
- And many more...

## 🔧 API Endpoints

### Core Endpoints
- `POST /api/v1/journey-analysis` - Comprehensive journey analysis
- `GET /api/v1/delays/histogram` - Demo histogram data
- `POST /api/v1/ai-analysis` - AI-powered analysis

### Cache Management
- `GET /api/v1/cache/stats` - Cache statistics
- `GET /api/v1/cache/metrics` - Cached metrics data
- `GET /api/v1/cache/services` - Cached service requests

### Health & Status
- `GET /health` - Health check
- `GET /` - API information

## 🎨 Customization

### Frontend Styling
The application uses a modern dark theme with customizable CSS variables. Key styling files:
- `frontend/src/App.css` - Main application styles
- Component-specific styling is embedded within React components

### Backend Configuration
- Modify timeout settings in `main.py`
- Adjust caching behavior in `cache_manager.py`
- Update station codes in `station_codes.json`

## 📊 Data Sources

- **HSP API**: Historical Service Performance data from UK rail operators
- **Station Codes**: Official UK railway station identifiers
- **OpenAI**: AI-powered analysis and insights

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational and research purposes. Performance data is historical and may not reflect current service levels. Always check official railway sources for live travel information.

## 🙏 Acknowledgments

- UK Railway operators for providing historical performance data
- OpenAI for AI analysis capabilities
- The open-source community for the fantastic tools and libraries used

---

**Built with ❤️ for railway enthusiasts and data analysts**