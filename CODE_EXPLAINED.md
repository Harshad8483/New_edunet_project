# Code Structure & Explanation

## Backend (`main.py`)
The backend is built with **FastAPI**. Here are the key components:

### 1. Initialization
- **`app = FastAPI()`**: Creates the web server instance.
- **CORS Middleware**: Allows the React frontend to communicate with the Python backend securely.
- **Global Stores**: `data_store` (Pandas DataFrame) and `model_store` (ML Model) hold the current state in memory.

### 2. Startup Event
- **`@app.on_event("startup")`**: Runs once when the server starts. It attempts to load `electricity_data.csv` and the `electricity_model.pkl` file so the app is ready immediately.

### 3. API Endpoints
- **`GET /api/stats`**: Calculates summary statistics using Pandas (Mean, Max, Last Value).
- **`GET /api/trends`**: Returns usage data formatted for the charts.
- **`GET /api/predict`**:
    - Takes the last recorded usage.
    - Feeds it into the ML model (`model.predict()`).
    - Calculates **Estimated Bill** ($0.15/kWh rate).
    - Calculates **CO2 Emissions** (0.4kg/kWh factor).
    - Derives the **Green Score** based on efficiency comparisons.
- **`POST /api/upload`**:
    - Accepts a CSV file upload.
    - Uses `pd.read_csv` to parse it.
    - Renames columns to standard names (`date`, `usage`) to ensure compatibility regardless of the input format.

---

## Frontend (`src/`)
The frontend uses **React** + **Vite**.

### 1. `App.jsx` (Main Controller)
- Manages state (`stats`, `trends`, `prediction`) using `useState`.
- Fetches initial data via `useEffect` on page load.
- Handles file uploads and orchestrates the view switching (Dashboard vs. Analysis tab).

### 2. Components
- **`Sidebar.jsx`**: Navigation menu. Uses Framer Motion for the active tab sliding indicator.
- **`KPICard.jsx`**: Reusable card for displaying metrics. Features "counting up" animation for numbers.
- **`UsageChart.jsx`**: Wraps the `recharts` library. It intelligently switches between Line and Bar charts based on the `type` prop.
- **`PredictionPanel.jsx`**: Visualizes the AI results. Contains the circular progress gauge for the Green Score.

### 3. Styling (`index.css` & Tailwind)
- We use **Tailwind CSS** for all styling.
- **Theme**: A custom "slate" and "emerald" palette defines the app's dark, eco-friendly look.
- **Animations**: `framer-motion` handles the smooth entry/exit animations for pages and cards.
