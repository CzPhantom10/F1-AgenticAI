# 🏎️ PitWall AI – Formula 1 Intelligence Platform

PitWall AI is an AI-powered Formula 1 analytics platform that combines historical race data, championship standings, constructor performance, circuit intelligence, and predictive insights into a single command center.

Users can explore Formula 1 seasons, analyze driver and constructor performance, compare careers, evaluate track-specific statistics, and interact with an AI analyst capable of answering natural-language questions about Formula 1.

---

## 🚀 Features

### 📊 Championship Dashboard

* Live Driver Standings
* Live Constructor Standings
* Championship Leader Tracking
* Last Race Results
* Next Race Information
* Season Overview Metrics

### 👨‍🏎️ Driver Analytics

* Multi-season Driver Standings (2018–2026)
* Career Performance Analysis
* Wins, Podiums, Points
* Driver Comparison Engine
* Historical Driver Rankings

### 🏁 Constructor Analytics

* Multi-season Constructor Standings
* Team Performance Tracking
* Constructor Comparisons
* Historical Championship Data

### 🌍 Circuit Intelligence

Track-specific analytics including:

* Silverstone
* Monaco
* Spa-Francorchamps
* Monza
* Suzuka
* Zandvoort
* And more

Metrics include:

* Wins
* Podiums
* Average Finish
* Driver Rankings
* Constructor Rankings

### 🤖 AI Analyst (Groq Powered)

Users can ask natural language questions such as:

* "Who performs best at Silverstone?"
* "Compare Hamilton and Verstappen career stats"
* "Which constructor dominates Monaco?"
* "Show Verstappen career summary"
* "Predict the winner of the British Grand Prix"

The AI dynamically selects relevant datasets and generates contextual explanations.

### 🔮 Race Prediction Engine

Prediction model uses:

* Recent Driver Form
* Historical Circuit Performance
* Constructor Strength
* Championship Momentum
* Track-Specific Performance Trends

Outputs:

* Predicted Winner
* Confidence Score
* Supporting Statistics
* Explanation of Prediction Factors

---

## 🧠 AI Capabilities

PitWall AI supports:

### Driver Queries

* Career summaries
* Career comparisons
* Driver rankings
* Performance trends

### Constructor Queries

* Team comparisons
* Historical dominance
* Circuit-specific performance

### Circuit Queries

* Best driver at a track
* Best constructor at a track
* Historical track performance

### Prediction Queries

* Race winner predictions
* Podium predictions
* Championship outlook analysis

---

## 🛠️ Tech Stack

### Frontend

* React.js
* TypeScript
* Tailwind CSS
* Framer Motion

### Backend

* FastAPI
* Python

### Data Processing

* FastF1
* Ergast Historical F1 Database
* Pandas
* NumPy

### AI Layer

* Groq API
* LLM-powered Query Routing
* Context-Aware Data Retrieval

### Database

* SQLite / PostgreSQL

---

## 📂 Project Structure

```bash
pitwall-ai/
│
├── frontend/
│   ├── dashboard
│   ├── drivers
│   ├── constructors
│   ├── races
│   └── analyst
│
├── backend/
│   ├── api
│   ├── services
│   ├── analytics
│   ├── prediction
│   └── database
│
├── data/
│   ├── historical_data
│   ├── circuit_memory
│   └── standings
│
└── README.md
```

---

## 📈 Data Sources

### FastF1

Provides:

* Race Results
* Qualifying Data
* Timing Information
* Session Statistics

### Ergast API

Provides:

* Historical Seasons
* Driver Records
* Constructor Records
* Championship Data

Coverage:
**2018 – 2026**

---

## 🎯 Use Cases

### Fans

* Explore F1 history
* Compare drivers
* Analyze teams

### Analysts

* Track-specific performance studies
* Championship trend analysis
* Race predictions

### Students & Developers

* Learn sports analytics
* Learn AI-powered retrieval systems
* Understand sports intelligence platforms

---

## 🔥 Example Questions

```text
Who performs best at Silverstone?

Compare Hamilton and Verstappen career stats.

Which constructor dominates Monaco?

Show Leclerc's career summary.

Predict the winner of the British Grand Prix.

Why is Mercedes stronger than Ferrari this season?

Who has the highest average finish at Monza?
```

---

## Future Improvements

* Telemetry Visualization
* Lap-by-Lap Analytics
* Interactive Driver Performance Charts
* AI Strategy Simulator
* Pit Stop Optimization Models
* Championship Probability Forecasting
* Real-Time Race Weekend Analysis

---

## Authors

Developed as part of a hackathon project focused on combining:

* Sports Analytics
* Historical Data Intelligence
* Large Language Models
* Predictive Analytics

to create a next-generation Formula 1 Intelligence Platform.

---

### 🏆 PitWall AI

**Race Intelligence. Lap by Lap.**
