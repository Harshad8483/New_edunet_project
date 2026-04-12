from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import shutil
import pandas as pd
import numpy as np
import pickle
import os
from datetime import datetime, timedelta
from pydantic import BaseModel

app = FastAPI(title="GreenAI Electricity Analyzer")

# Currency conversion (approximate, used for display only)
USD_TO_INR = 82.0  # update as needed; approximation for INR display

def calculate_indian_bill(kwh: float) -> float:
    bill = 0.0
    val = max(0.0, float(kwh))
    if val <= 100: bill += val * 3.00
    elif val <= 200: bill += (100 * 3.00) + ((val - 100) * 4.50)
    elif val <= 400: bill += (100 * 3.00) + (100 * 4.50) + ((val - 200) * 6.50)
    else: bill += (100 * 3.00) + (100 * 4.50) + (200 * 6.50) + ((val - 400) * 8.00)
    return bill + 150.0  # + fixed generic charge

# CORS Setup
# Allow any localhost origin (different ports used by Vite during development)
# CORS Setup (UPDATED FOR DEPLOYMENT)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all (for deployment)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to store data and model
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "electricity_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "electricity_model.pkl")

data_store = None
model_store = None

# Training status tracking
training_state = {
    "is_training": False,
    "last_trained": None,
    "last_metrics": None
}


def train_model_from_df(df, features=None):
    """Backward-compatible trainer for in-memory dataframe. Saves df to a temporary CSV and calls the incremental trainer.

    This helps ensure all training uses the same robust, chunked pipeline that scales to large files.
    """
    import tempfile
    tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    df.to_csv(tmpf.name, index=False)
    tmpf.close()
    return train_model_from_path(tmpf.name, features=features)


def train_model_from_path(path, features=None, chunk_size=10000):
    """Train model incrementally from a CSV on disk using chunks to handle large datasets.

    - Uses SGDRegressor for incremental learning and StandardScaler.partial_fit for online scaling.
    - Extracts simple time features if `date` column exists (hour, dow).
    - Reports progress via `training_state['progress']` (0-100).

    Returns: metrics dict like {"mse":..., "r2":..., "rows": N, "features": [...]}
    """
    global model_store, training_state
    try:
        from sklearn.linear_model import SGDRegressor
        from sklearn.preprocessing import StandardScaler

        training_state['is_training'] = True
        training_state['progress'] = 0
        training_state['last_metrics'] = None

        # Estimate number of rows for progress using a quick line count (fast and memory-friendly)
        total_rows = 0
        with open(path, 'rb') as f:
            for i, _ in enumerate(f):
                total_rows += 1
        total_rows = max(0, total_rows - 1)  # subtract header
        if total_rows == 0:
            training_state['is_training'] = False
            training_state['last_metrics'] = {"mse": None, "r2": None, "rows": 0}
            return training_state['last_metrics']

        scaler = StandardScaler()
        model = SGDRegressor(max_iter=1, tol=None, learning_rate='invscaling', eta0=0.01, random_state=42)

        # Running metrics for incremental evaluation
        n_seen = 0
        mean_y = 0.0
        sse = 0.0
        sst = 0.0

        prev_last_usage = None
        chosen_features = None

        rows_processed = 0

        for chunk in pd.read_csv(path, chunksize=chunk_size, sep=None, engine='python'):
            # Column normalization for chunk
            if 'usage' not in chunk.columns:
                # try to map common names to 'usage'
                for cand in ['Electricity_Consumption', 'Electricity_Consumed', 'Consumption', 'consumption_kwh', 'kWh']:
                    if cand in chunk.columns:
                        chunk.rename(columns={cand: 'usage'}, inplace=True)
                        break
                # if still missing, find first numeric column
                if 'usage' not in chunk.columns:
                    numeric_cols = chunk.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        chunk.rename(columns={numeric_cols[0]: 'usage'}, inplace=True)
            # date parsing and derived features
            if 'date' in chunk.columns:
                try:
                    chunk['date'] = pd.to_datetime(chunk['date'])
                    chunk['hour'] = chunk['date'].dt.hour
                    chunk['dow'] = chunk['date'].dt.dayofweek
                except Exception:
                    pass

            # prev_usage across chunk boundaries
            if prev_last_usage is not None and 'prev_usage' not in chunk.columns:
                # set first row prev_usage
                if len(chunk) > 0:
                    first_idx = chunk.index[0]
                    chunk.loc[first_idx, 'prev_usage'] = prev_last_usage
            chunk['prev_usage'] = chunk['usage'].shift(1)

            # drop rows lacking required fields
            if 'usage' not in chunk.columns:
                rows_processed += len(chunk)
                training_state['progress'] = int((rows_processed / total_rows) * 100)
                continue

            chunk = chunk.dropna(subset=['usage', 'prev_usage'])
            if len(chunk) == 0:
                rows_processed += len(chunk)
                training_state['progress'] = int((rows_processed / total_rows) * 100)
                continue

            if chosen_features is None:
                candidate = ['prev_usage', 'Avg_Past_Consumption', 'Temperature', 'hour', 'dow']
                chosen_features = [f for f in candidate if f in chunk.columns]
                if 'prev_usage' not in chosen_features:
                    chosen_features.insert(0, 'prev_usage')

            X_chunk = chunk[chosen_features].astype(float)
            y_chunk = chunk['usage'].astype(float)

            # Online scaling and model update
            scaler.partial_fit(X_chunk)
            Xs = scaler.transform(X_chunk)
            model.partial_fit(Xs, y_chunk)

            preds = model.predict(Xs)

            # Incremental metrics (online mean + sse/sst)
            for yi, pi in zip(y_chunk.values, preds):
                n_seen += 1
                delta = yi - mean_y
                mean_y += delta / n_seen
                sse += (yi - pi) ** 2
                sst += delta * (yi - mean_y)

            prev_last_usage = chunk['usage'].iloc[-1]
            rows_processed += len(chunk)
            training_state['progress'] = int((rows_processed / total_rows) * 100)

        mse = float(sse / max(1, n_seen))
        r2 = float(1 - sse / max(1e-12, sst)) if sst != 0 else 1.0

        # Save trained artifacts
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump({'model': model, 'scaler': scaler, 'features': chosen_features}, f)

        model_store = {'model': model, 'scaler': scaler, 'features': chosen_features}

        training_state['is_training'] = False
        training_state['progress'] = 100
        training_state['last_trained'] = datetime.utcnow().isoformat()
        training_state['last_metrics'] = {"mse": mse, "r2": r2, "rows": rows_processed, "features": chosen_features}

        print(f"Incremental model trained and saved. rows={rows_processed}, features={chosen_features}")
        return training_state['last_metrics']

    except Exception as e:
        training_state['is_training'] = False
        training_state['last_metrics'] = {"error": str(e)}
        print(f"Error in incremental training: {e}")
        return training_state['last_metrics']

# Initialize data and model on startup
@app.on_event("startup")
async def startup_event():
    global data_store, model_store

    print("🚀 Starting backend safely...")

    try:
        if os.path.exists(DATA_PATH):
            data_store = pd.read_csv(DATA_PATH)

            if 'date' in data_store.columns:
                data_store['date'] = pd.to_datetime(
                    data_store['date'], errors='coerce'
                )

            print("✅ Data loaded")
        else:
            data_store = None

    except Exception as e:
        print(f"❌ Data load error: {e}")
        data_store = None

    try:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, 'rb') as f:
                loaded = pickle.load(f)

            if isinstance(loaded, dict):
                model_store = loaded
            else:
                model_store = {'model': loaded, 'features': ['prev_usage']}

            print("✅ Model loaded")
        else:
            model_store = None

    except Exception as e:
        print(f"❌ Model load error: {e}")
        model_store = None

class PredictionResponse(BaseModel):
    predicted_usage: float
    estimated_bill: float
    estimated_bill_inr: float = None
    estimated_monthly_bill: float = None
    estimated_monthly_bill_inr: float = None
    co2_emissions: float
    green_score: float
    unit: str = "kWh"

@app.get("/")
def read_root():
    return {"message": "Welcome to GreenAI Energy Analyzer API"}

@app.get("/api/stats")
def get_stats():
    global data_store
    # Prefer the lightweight in-memory preview if available, otherwise summarize on disk
    if data_store is None:
        if os.path.exists(DATA_PATH):
            summary = summarize_csv(DATA_PATH, preview_n=1)
            if summary['rows'] == 0:
                return JSONResponse(status_code=404, content={"message": "No usable data found in file"})
            stats = {
                "average_usage": float(summary['average_usage']) if summary['average_usage'] is not None else None,
                "peak_usage": float(summary['peak_usage']) if summary['peak_usage'] is not None else None,
                "last_recorded": float(summary['last_recorded']) if summary['last_recorded'] is not None else None,
                "total_readings": int(summary['rows'])
            }
            return stats
        return JSONResponse(status_code=404, content={"message": "No data available"})
    
    usage = data_store['usage']
    
    stats = {
        "average_usage": float(usage.mean()),
        "peak_usage": float(usage.max()),
        "last_recorded": float(usage.iloc[-1]),
        "total_readings": len(usage)
    }
    return stats

@app.get("/api/trends")
def get_trends():
    global data_store
    # If we don't have an in-memory preview, build one via summarizing the CSV (streaming)
    if data_store is None:
        if os.path.exists(DATA_PATH):
            summary = summarize_csv(DATA_PATH, preview_n=1000)
            records = summary['preview']
            # format date strings nicely
            for r in records:
                if r.get('date'):
                    try:
                        r['date'] = pd.to_datetime(r['date']).isoformat()
                    except Exception:
                        r['date'] = str(r.get('date'))
            return records
        return JSONResponse(status_code=404, content={"message": "No data available"})
    
    # Return data for charts (last 1000 points to support proper filtering)
    recent_data = data_store.tail(1000).copy()
    recent_data['date'] = recent_data['date'].apply(lambda x: x.isoformat() if pd.notnull(x) else None)
    records = recent_data[['date', 'usage']].to_dict(orient='records')
    return records


@app.get('/api/insights')
def get_insights():
    """Return computed AI-driven insights for UI display."""
    # Prefer full file if available
    if os.path.exists(DATA_PATH):
        insights = compute_insights_from_path(DATA_PATH)
    else:
        # Fallback to in-memory small preview
        if data_store is None:
            return JSONResponse(status_code=404, content={"message": "No data available for insights"})
        # use the small in-memory dataset to compute quick insights
        # write to a temp file and reuse existing path-based function
        import tempfile
        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        data_store.to_csv(tmpf.name, index=False)
        tmpf.close()
        insights = compute_insights_from_path(tmpf.name)
        try:
            os.remove(tmpf.name)
        except Exception:
            pass

    # Add human-friendly text messages
    insights['peak_message'] = f"Highest electricity usage occurs during {insights.get('peak_period', 'unknown')}."
    insights['spike_insight'] = insights.get('appliance_message')
    # Add rupee equivalent to savings estimate and update message to INR
    insights['saving_estimate_rupees'] = round((insights.get('saving_estimate_dollars', 0) * USD_TO_INR), 2)
    if insights.get('saving_pct', 0) > 0:
        insights['savings_message'] = f"Reducing peak usage could save approximately {insights['saving_pct']}% (~₹{insights['saving_estimate_rupees']})."
    else:
        insights['savings_message'] = "Predicted usage is at or below historical average; limited short-term saving opportunities detected."
    insights['env_message'] = f"Carbon emission trend is {insights['env_trend']} (change {insights['env_pct_change']}%)."

    return insights

@app.get("/api/predict", response_model=PredictionResponse)
def predict_next():
    global data_store, model_store
    # If we don't have any data, return clear error
    if data_store is None:
        return JSONResponse(status_code=404, content={"message": "No data available to predict"})

    last_usage = data_store['usage'].iloc[-1]
    avg_usage = data_store['usage'].mean()

    # If model isn't trained yet, return a sensible fallback prediction (historical average)
    if model_store is None:
        prediction = float(avg_usage) if np.isfinite(avg_usage) else float(last_usage)
        # Estimate monthly using inferred sampling interval (handles hourly/daily/weekly datasets)
        median_diff_hours = None
        try:
            if 'date' in data_store.columns and len(data_store) >= 2:
                dates = data_store['date'].sort_values()
                diffs = dates.diff().dt.total_seconds().dropna() / 3600.0
                if len(diffs) > 0:
                    median_diff_hours = float(diffs.median())
        except Exception:
            median_diff_hours = None

        if not median_diff_hours or median_diff_hours <= 0:
            median_diff_hours = 24.0  # fallback to daily readings

        readings_per_day = max(1.0, 24.0 / median_diff_hours)
        monthly_multiplier = readings_per_day * 30.0

        predicted_monthly_kwh = prediction * monthly_multiplier
        estimated_monthly_bill_inr = calculate_indian_bill(predicted_monthly_kwh)
        estimated_monthly_bill = estimated_monthly_bill_inr / USD_TO_INR
        
        estimated_bill_inr = estimated_monthly_bill_inr / max(1.0, monthly_multiplier)
        estimated_bill = estimated_monthly_bill / max(1.0, monthly_multiplier)

        # Monthly CO2 Impact (Indian average ~0.82 kg/kWh)
        co2_emissions = predicted_monthly_kwh * 0.82

        if avg_usage > 0:
            diff_pct = (avg_usage - prediction) / avg_usage
            raw_score = 70 + (diff_pct * 40)
        else:
            raw_score = 50
        green_score = max(0, min(100, raw_score))
        return {
            "predicted_usage": float(prediction),
            "estimated_bill": float(estimated_bill),
            "estimated_bill_inr": float(estimated_bill_inr),
            "estimated_monthly_bill": float(estimated_monthly_bill),
            "estimated_monthly_bill_inr": float(estimated_monthly_bill_inr),
            "co2_emissions": float(co2_emissions),
            "green_score": float(green_score)
        }

    # Prepare features for model
    features = []
    model_obj = model_store
    model = None
    feature_order = ['prev_usage']

    if isinstance(model_obj, dict) and 'model' in model_obj:
        model = model_obj['model']
        feature_order = model_obj.get('features', ['prev_usage'])
    else:
        # legacy estimator
        model = model_obj
        feature_order = ['prev_usage']

    # Build input row aligned with the trained features
    input_row = {}
    input_row['prev_usage'] = last_usage
    # include other features if available
    if 'Avg_Past_Consumption' in data_store.columns:
        input_row['Avg_Past_Consumption'] = data_store['Avg_Past_Consumption'].iloc[-1]
    if 'Temperature' in data_store.columns:
        input_row['Temperature'] = data_store['Temperature'].iloc[-1]

    # Build input array aligned to the trained feature order
    X_row = np.array([[float(input_row.get(f, last_usage)) for f in feature_order]])

    # If we have an online scaler saved, apply it before predicting
    if isinstance(model_obj, dict) and 'scaler' in model_obj and model_obj['scaler'] is not None:
        scaler = model_obj['scaler']
        try:
            X_row = scaler.transform(X_row)
        except Exception:
            # if scaler expects 2D with same columns, try building DataFrame
            try:
                import pandas as _pd
                Xdf = _pd.DataFrame([input_row])[feature_order].astype(float)
                X_row = scaler.transform(Xdf.values)
            except Exception:
                pass

    prediction = model.predict(X_row)[0]

    # Basic sanity checks / fallback to average if non-finite
    try:
        if not np.isfinite(prediction):
            raise ValueError("Non-finite prediction")
    except Exception:
        prediction = float(avg_usage)

    # Clip prediction to a reasonable range based on historical data
    min_usage = float(data_store['usage'].min())
    max_usage = float(data_store['usage'].max())
    lower_bound = max(0.0, min_usage * 0.5)
    upper_bound = max(avg_usage * 5.0, max_usage * 2.0, min_usage + 1e-6)

    if prediction < lower_bound or prediction > upper_bound:
        # If model output is out-of-bounds, fall back to average usage
        prediction = float(max(lower_bound, min(prediction, upper_bound)))

    # Calculations

    # Infer sampling interval to produce monthly estimate (handles hourly/daily/weekly datasets)
    median_diff_hours = None
    try:
        if 'date' in data_store.columns and len(data_store) >= 2:
            dates = data_store['date'].sort_values()
            diffs = dates.diff().dt.total_seconds().dropna() / 3600.0
            if len(diffs) > 0:
                median_diff_hours = float(diffs.median())
    except Exception:
        median_diff_hours = None

    if not median_diff_hours or median_diff_hours <= 0:
        median_diff_hours = 24.0  # fallback to daily readings

    readings_per_day = max(1.0, 24.0 / median_diff_hours)
    monthly_multiplier = readings_per_day * 30.0

    # Predicted monthly kWh (based on one-step prediction) and historical monthly kWh (from avg)
    predicted_monthly_kwh = prediction * readings_per_day * 30.0
    historical_monthly_kwh = avg_usage * readings_per_day * 30.0

    # Blend predicted with historical to avoid unrealistically low monthly estimates.
    # If we have a model confidence (r2) use it to weight the blend; otherwise use conservative default.
    try:
        r2 = training_state.get('last_metrics', {}).get('r2') if 'training_state' in globals() else None
        if r2 is None:
            alpha = 0.6
        else:
            # map r2 [0,1] to alpha between 0.3 and 0.9 (more confidence shifts toward prediction)
            alpha = 0.3 + 0.6 * float(min(1.0, max(0.0, r2)))
    except Exception:
        alpha = 0.6

    blended_monthly_kwh = (alpha * predicted_monthly_kwh) + ((1.0 - alpha) * historical_monthly_kwh)
    
    estimated_monthly_bill_inr = calculate_indian_bill(blended_monthly_kwh)
    estimated_monthly_bill = estimated_monthly_bill_inr / USD_TO_INR
    
    monthly_multiplier = readings_per_day * 30.0
    estimated_bill_inr = estimated_monthly_bill_inr / max(1.0, monthly_multiplier)
    estimated_bill = estimated_monthly_bill / max(1.0, monthly_multiplier)

    # Monthly CO2 Impact (Indian average ~0.82 kg/kWh)
    co2_emissions = blended_monthly_kwh * 0.82

    # Green Score Calculation (Simple Heuristic)
    # If prediction is lower than average, score is higher (more efficient)
    # Baseline score 70. Adjust by % difference from average.
    if avg_usage > 0:
        diff_pct = (avg_usage - prediction) / avg_usage
        raw_score = 70 + (diff_pct * 40)  # +10% efficiency -> +4 points
    else:
        raw_score = 50

    green_score = max(0, min(100, raw_score))
    
    return {
        "predicted_usage": float(prediction),
        "estimated_bill": float(estimated_bill),
        "estimated_bill_inr": float(estimated_bill_inr),
        "estimated_monthly_bill": float(estimated_monthly_bill),
        "estimated_monthly_bill_inr": float(estimated_monthly_bill_inr),
        "co2_emissions": float(co2_emissions),
        "green_score": float(green_score)
    }


@app.post("/api/train")
def train_endpoint(background_tasks: BackgroundTasks, run_sync: bool = Form(False)):
    """Trigger model retraining on the currently loaded `data_store`.

    By default this schedules incremental training in background and returns immediately. If `run_sync` is true (for debugging), training will run synchronously (not recommended for large files).
    """
    global data_store
    if data_store is None or not os.path.exists(DATA_PATH):
        return JSONResponse(status_code=404, content={"message": "No data available to train on"})

    if run_sync:
        # Run synchronously (blocking) - intended for debugging
        metrics = train_model_from_path(DATA_PATH)
        return {"message": "Training completed", "metrics": metrics}

    # schedule background job
    background_tasks.add_task(_background_retrain_from_disk)
    return JSONResponse(status_code=202, content={"message": "Training scheduled in background"})


@app.get("/api/train/status")
def train_status():
    """Return the current training status and last metrics."""
    return training_state

@app.post("/api/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), usage_column: str = None, date_column: str = None):
    """Save uploaded CSV to disk and schedule background retraining to avoid blocking the request.

    Optional form fields:
      - usage_column: override which column should be treated as 'usage'
      - date_column: override which column should be treated as 'date'
    """
    global data_store
    try:
        # Stream-upload to disk to avoid holding the entire file in memory
        with open(DATA_PATH, 'wb') as out_file:
            shutil.copyfileobj(file.file, out_file)

        # Light validation (read minimal portion using pandas) with robust dialect/header detection
        try:
            import csv
            with open(DATA_PATH, 'rb') as f:
                sample_bytes = f.read(65536)
            sample_text = sample_bytes.decode('utf-8', errors='replace')
            try:
                dialect = csv.Sniffer().sniff(sample_text)
                sep = dialect.delimiter
                has_header = csv.Sniffer().has_header(sample_text)
            except Exception:
                sep = None
                has_header = True

            # Read sample using detected settings
            try:
                if has_header:
                    sample = pd.read_csv(DATA_PATH, nrows=10, sep=sep, engine='python' if sep else 'python', encoding='utf-8', on_bad_lines='skip')
                else:
                    sample = pd.read_csv(DATA_PATH, nrows=10, header=None, sep=sep, engine='python', encoding='utf-8', on_bad_lines='skip')
                    # assign temporary header names
                    sample.columns = [f'col_{i}' for i in range(len(sample.columns))]
            except Exception:
                # fallback to liberal read
                sample = pd.read_csv(DATA_PATH, nrows=10, sep=None, engine='python', encoding='latin1', on_bad_lines='skip')

            # If sample columns look like actual data (headerless), re-read headerless
            def looks_like_headerless(df_sample):
                test_count = 0
                parseable_count = 0
                for c in df_sample.columns:
                    test_count += 1
                    try:
                        pd.to_datetime(c)
                        parseable_count += 1
                        continue
                    except Exception:
                        pass
                    try:
                        float(str(c))
                        parseable_count += 1
                    except Exception:
                        pass
                return parseable_count >= max(1, int(0.5 * test_count))

            if looks_like_headerless(sample):
                # treat as headerless
                sample = pd.read_csv(DATA_PATH, nrows=10, header=None, sep=sep, engine='python', encoding='utf-8', on_bad_lines='skip')
                sample.columns = [f'col_{i}' for i in range(len(sample.columns))]

        except Exception as e:
            # remove invalid file
            try:
                os.remove(DATA_PATH)
            except Exception:
                pass
            return JSONResponse(status_code=400, content={"message": f"Invalid CSV format: {str(e)}"})

        # Map common columns to internal standard names before loading the full file
        column_mapping = {
            'Timestamp': 'date',
            'Date': 'date',
            'Electricity_Consumption': 'usage',
            'Electricity_Consumed': 'usage',
            'Electricity_Used': 'usage',
            'Consumption': 'usage',
            'consumption_kwh': 'usage',
            'kWh': 'usage',
            'usage': 'usage'
        }

        # If user provided explicit columns use those
        if usage_column:
            column_mapping[usage_column] = 'usage'
        if date_column:
            column_mapping[date_column] = 'date'

        # Apply mapping on sample to confirm we can find a usage-like column
        sample_renamed = sample.rename(columns=column_mapping)

        # If sample appears headerless (columns are parseable values), try to interpret columns as values
        def _ensure_usage_from_sample(df_sample):
            # if 'usage' present, good
            if 'usage' in df_sample.columns:
                return 'usage'
            # If columns names are parseable as values, try headerless treatment
            parseable_cols = []
            for c in df_sample.columns:
                try:
                    pd.to_datetime(c)
                    parseable_cols.append(c)
                    continue
                except Exception:
                    pass
                try:
                    float(str(c))
                    parseable_cols.append(c)
                except Exception:
                    pass
            if len(parseable_cols) >= max(1, int(0.5 * len(df_sample.columns))):
                # assume second column is usage when headerless (common pattern)
                if len(df_sample.columns) >= 2:
                    guessed = df_sample.columns[1]
                    return guessed
            # fallback: find numeric dtype column
            numeric_cols = df_sample.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                return numeric_cols[0]
            return None

        guessed = _ensure_usage_from_sample(sample_renamed)
        if guessed is None:
            # remove invalid file
            try:
                os.remove(DATA_PATH)
            except Exception:
                pass
            return JSONResponse(status_code=400, content={"message": "Invalid CSV format. No usage-like numeric column found."})
        # If guessed wasn't already mapped, map it
        if guessed not in column_mapping or column_mapping.get(guessed) != 'usage':
            column_mapping[guessed] = 'usage'

        # Try to detect delimiter and header using csv.Sniffer then rewrite normalized CSV to disk
        import csv
        import tempfile

        # Read a small sample to detect dialect
        with open(DATA_PATH, 'rb') as f:
            sample_bytes = f.read(65536)
        try:
            sample_text = sample_bytes.decode('utf-8', errors='replace')
            dialect = csv.Sniffer().sniff(sample_text)
            sep = dialect.delimiter
            has_header = csv.Sniffer().has_header(sample_text)
        except Exception:
            sep = None
            has_header = True

        # Read file with pandas using detected sep (or let pandas detect)
        # If sample suggested headerless, read with header=None so we don't treat first row as column names
        headerless = False
        try:
            # Quick check: use same detection as earlier sample header inference
            import csv as _csv
            sample_text = sample_text if 'sample_text' in locals() else open(DATA_PATH, 'rb').read(65536).decode('utf-8', errors='replace')
            try:
                headerless = not _csv.Sniffer().has_header(sample_text)
            except Exception:
                headerless = False
        except Exception:
            headerless = False

        try:
            if sep:
                full_df = pd.read_csv(DATA_PATH, header=None if headerless else 'infer', sep=sep, engine='python', encoding='utf-8', on_bad_lines='skip')
            else:
                full_df = pd.read_csv(DATA_PATH, header=None if headerless else 'infer', sep=None, engine='python', encoding='utf-8', on_bad_lines='skip')
        except Exception:
            # fallback with latin1
            full_df = pd.read_csv(DATA_PATH, header=None if headerless else 'infer', sep=None, engine='python', encoding='latin1', on_bad_lines='skip')

        # Apply mapping (rename columns) and handle headerless files
        if headerless:
            # assign reasonable names: if 2+ columns, treat first as date, second as usage
            colnames = list(full_df.columns)
            if len(colnames) >= 2:
                rename_map = {colnames[0]: 'date', colnames[1]: 'usage'}
                full_df.rename(columns=rename_map, inplace=True)
            else:
                # single-column file -> treat as usage
                full_df.rename(columns={colnames[0]: 'usage'}, inplace=True)
        else:
            full_df.rename(columns=column_mapping, inplace=True)

        # Ensure date column exists or create default
        if 'date' in full_df.columns:
            try:
                full_df['date'] = pd.to_datetime(full_df['date'])
            except Exception:
                full_df['date'] = pd.date_range(end=datetime.now(), periods=len(full_df), freq='D')
        else:
            full_df['date'] = pd.date_range(end=datetime.now(), periods=len(full_df), freq='D')

        # Ensure usage column exists
        if 'usage' not in full_df.columns:
            numeric_cols = full_df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                full_df.rename(columns={numeric_cols[0]: 'usage'}, inplace=True)

        if 'usage' not in full_df.columns:
            try:
                os.remove(DATA_PATH)
            except Exception:
                pass
            return JSONResponse(status_code=400, content={"message": "Upload failed: no usable 'usage' column detected in CSV."})

        # Save normalized CSV back to disk with comma separator
        try:
            full_df.to_csv(DATA_PATH, index=False)
        except Exception:
            # last resort: save using pandas safe write
            tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', dir=BASE_DIR)
            full_df.to_csv(tmpf.name, index=False)
            tmpf.close()
            os.replace(tmpf.name, DATA_PATH)

        # Summarize dataset in streaming fashion to provide quick UI feedback without loading whole file
        summary = summarize_csv(DATA_PATH, preview_n=30)

        # Build a minimal in-memory preview `data_store` so UI calls like /api/trends and /api/stats work quickly.
        # We don't keep the full dataset in memory for large uploads.
        df_preview = pd.DataFrame(summary['preview'])
        if 'date' in df_preview.columns:
            try:
                df_preview['date'] = pd.to_datetime(df_preview['date'])
            except Exception:
                df_preview['date'] = pd.date_range(end=datetime.now(), periods=len(df_preview), freq='D')
        else:
            df_preview['date'] = pd.date_range(end=datetime.now(), periods=len(df_preview), freq='D')

        # Save lightweight preview for UI. Full training will still happen in background.
        data_store = df_preview

        # Schedule background retraining in a separate thread to avoid blocking the server
        import threading
        threading.Thread(target=_background_retrain_from_disk, daemon=True).start()

        return {"message": "File uploaded and saved. Training scheduled in background.", "rows": summary['rows'], "columns": list(full_df.columns)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"Upload failed: {str(e)}"})


def _background_retrain_from_disk():
    """Helper run in a background thread/process to retrain the model from disk.

    This keeps the /api/upload response fast and offloads CPU-bound training work.
    Updates `training_state` with progress and errors.
    Uses chunked incremental training to scale to large datasets without high memory use.
    """
    global training_state
    try:
        print("Background training started...")
        training_state['is_training'] = True
        training_state['progress'] = 0
        if os.path.exists(DATA_PATH):
            metrics = train_model_from_path(DATA_PATH)
            training_state['is_training'] = False
            training_state['last_trained'] = datetime.utcnow().isoformat()
            training_state['last_metrics'] = metrics
            print(f"Background training finished: {metrics}")
        else:
            training_state['is_training'] = False
            training_state['last_metrics'] = {"error": "Data file missing"}
            print("Background training aborted: data file missing")
    except Exception as e:
        print(f"Background training error: {e}")
        training_state['is_training'] = False
        training_state['last_metrics'] = {"error": str(e)}


from collections import deque

# Helper: Suggest column mappings for a dataframe sample
def suggest_mappings_from_sample(df_sample):
    """Given a small dataframe sample, suggest the best column for 'usage' and 'date'."""
    # Candidate mapping keys
    column_mapping = {
        'Timestamp': 'date',
        'Date': 'date',
        'Electricity_Consumption': 'usage',
        'Electricity_Consumed': 'usage',
        'Electricity_Used': 'usage',
        'Consumption': 'usage',
        'consumption_kwh': 'usage',
        'kWh': 'usage',
        'usage': 'usage'
    }

    cols = list(df_sample.columns)

    suggested = {'usage': None, 'date': None}

    # First pass: direct matches
    for c in cols:
        if c in column_mapping:
            if column_mapping[c] == 'usage' and suggested['usage'] is None:
                suggested['usage'] = c
            if column_mapping[c] == 'date' and suggested['date'] is None:
                suggested['date'] = c

    # Second pass: look for numeric columns for usage
    if suggested['usage'] is None:
        numeric_cols = df_sample.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) > 0:
            suggested['usage'] = numeric_cols[0]

    # Third pass: look for parsable date-like columns
    if suggested['date'] is None:
        for c in cols:
            try:
                pd.to_datetime(df_sample[c])
                suggested['date'] = c
                break
            except Exception:
                continue

    # Return the suggested mapping
    return suggested


def summarize_csv(path, preview_n=30, chunk_size=20000):
    """Read the CSV in streaming chunks and return lightweight summary and last `preview_n` rows.

    This avoids loading the entire dataset into memory for large files while still providing the UI with needed stats.
    Returns: { 'rows': int, 'average_usage': float, 'peak_usage': float, 'last_recorded': float, 'preview': list of rows }
    """
    total = 0
    sum_usage = 0.0
    peak = None
    last_val = None
    last_rows = deque(maxlen=preview_n)

    # We'll attempt to parse date when available
    for chunk in pd.read_csv(path, chunksize=chunk_size):
        # map typical column names to 'usage' if necessary
        if 'usage' not in chunk.columns:
            for cand in ['Electricity_Consumption', 'Electricity_Consumed', 'Consumption', 'consumption_kwh', 'kWh']:
                if cand in chunk.columns:
                    chunk.rename(columns={cand: 'usage'}, inplace=True)
                    break
            if 'usage' not in chunk.columns:
                numeric_cols = chunk.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    chunk.rename(columns={numeric_cols[0]: 'usage'}, inplace=True)

        if 'usage' not in chunk.columns:
            continue

        # reset index to keep consistent row order when grabbing last rows
        chunk = chunk.reset_index(drop=True)
        # try parse date if present
        if 'date' in chunk.columns:
            try:
                chunk['date'] = pd.to_datetime(chunk['date'])
            except Exception:
                pass

        chunk = chunk.dropna(subset=['usage'])
        if len(chunk) == 0:
            continue

        total += len(chunk)
        sum_usage += chunk['usage'].sum()
        chunk_max = float(chunk['usage'].max())
        peak = chunk_max if peak is None else max(peak, chunk_max)
        last_val = float(chunk['usage'].iloc[-1])

        # record last rows
        for _, r in chunk.tail(preview_n).iterrows():
            last_rows.append({'date': (r['date'].isoformat() if 'date' in r and pd.notna(r['date']) else None), 'usage': float(r['usage'])})

    avg = (sum_usage / total) if total > 0 else None
    preview = list(last_rows)
    return { 'rows': total, 'average_usage': avg, 'peak_usage': peak, 'last_recorded': last_val, 'preview': preview }


def compute_insights_from_path(path, chunk_size=20000):
    """Compute AI-driven insights from CSV by streaming through file. Returns a dict with:
    - peak_hour: int
    - peak_period: human-readable period
    - peak_hour_avg: float
    - spike_count: int
    - spike_rate_per_1000: float
    - appliance_message: str
    - saving_pct: float (percentage)
    - saving_estimate_dollars: float
    - env_trend: 'increasing'|'decreasing'|'stable'
    - env_pct_change: float

    Uses predicted usage from internal predict_next() when available.
    """
    # First pass: compute aggregates and hourly sums
    total = 0
    sum_usage = 0.0
    hour_sums = [0.0] * 24
    hour_counts = [0] * 24
    prev_val = None
    # Note: we don't compute spikes here because threshold requires avg

    for chunk in pd.read_csv(path, chunksize=chunk_size, sep=None, engine='python'):
        # normalize usage column
        if 'usage' not in chunk.columns:
            for cand in ['Electricity_Consumption', 'Electricity_Consumed', 'Consumption', 'consumption_kwh', 'kWh']:
                if cand in chunk.columns:
                    chunk.rename(columns={cand: 'usage'}, inplace=True)
                    break
            if 'usage' not in chunk.columns:
                numeric_cols = chunk.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    chunk.rename(columns={numeric_cols[0]: 'usage'}, inplace=True)
        if 'usage' not in chunk.columns:
            continue

        # parse date if present
        if 'date' in chunk.columns:
            try:
                chunk['date'] = pd.to_datetime(chunk['date'])
            except Exception:
                pass

        chunk = chunk.dropna(subset=['usage'])
        if len(chunk) == 0:
            continue

        total += len(chunk)
        sum_usage += chunk['usage'].sum()

        if 'date' in chunk.columns:
            hours = chunk['date'].dt.hour.fillna(0).astype(int)
            for h, val in zip(hours, chunk['usage']):
                hour_sums[h] += float(val)
                hour_counts[h] += 1
        else:
            # Distribute evenly if no date
            avg_val = chunk['usage'].mean()
            for h in range(24):
                hour_sums[h] += avg_val * len(chunk) / 24.0
                hour_counts[h] += int(len(chunk) / 24) if len(chunk) >= 24 else 1

    avg_usage = (sum_usage / total) if total > 0 else 0.0

    # Hourly averages
    hour_avgs = [(hour_sums[h] / hour_counts[h]) if hour_counts[h] > 0 else 0.0 for h in range(24)]
    peak_hour = int(max(range(24), key=lambda h: hour_avgs[h])) if total > 0 else None
    peak_hour_avg = hour_avgs[peak_hour] if peak_hour is not None else None

    # Map peak hour to period
    def hour_to_period(h):
        if h is None:
            return 'unknown'
        if 6 <= h <= 11:
            return 'morning hours'
        if 12 <= h <= 16:
            return 'afternoon hours'
        if 17 <= h <= 21:
            return 'evening hours'
        return 'night hours'

    peak_period = hour_to_period(peak_hour)

    # Second pass: detect spikes (sudden increases) based on threshold
    spike_threshold = max(5.0, avg_usage * 0.5)
    spike_count = 0
    total_rows = 0
    prev_val = None
    for chunk in pd.read_csv(path, chunksize=chunk_size, sep=None, engine='python'):
        # normalize usage
        if 'usage' not in chunk.columns:
            for cand in ['Electricity_Consumption', 'Electricity_Consumed', 'Consumption', 'consumption_kwh', 'kWh']:
                if cand in chunk.columns:
                    chunk.rename(columns={cand: 'usage'}, inplace=True)
                    break
            if 'usage' not in chunk.columns:
                numeric_cols = chunk.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    chunk.rename(columns={numeric_cols[0]: 'usage'}, inplace=True)

        chunk = chunk.dropna(subset=['usage'])
        if len(chunk) == 0:
            continue

        for val in chunk['usage'].astype(float):
            total_rows += 1
            if prev_val is not None:
                if (val - prev_val) > spike_threshold:
                    spike_count += 1
            prev_val = val

    spike_rate_per_1000 = (spike_count / total_rows * 1000.0) if total_rows > 0 else 0.0
    appliance_message = 'Usage pattern suggests frequent operation of high-load appliances.' if spike_rate_per_1000 > 1.0 else 'No frequent high-load appliance patterns detected.'

    # Predicted usage + cost-saving opportunity
    try:
        pred = predict_next()
        # if FastAPI returns a JSONResponse, access .body? But predict_next returns dict in normal flow
        if isinstance(pred, dict):
            predicted_usage = pred.get('predicted_usage', None)
            predicted_monthly_bill = pred.get('estimated_monthly_bill', None)
        else:
            predicted_usage = None
            predicted_monthly_bill = None
    except Exception:
        predicted_usage = None
        predicted_monthly_bill = None

    saving_pct = 0.0
    saving_estimate_dollars = 0.0
    # If predicted usage is higher than historical average, estimate potential saving by reducing to average
    if predicted_usage is not None and predicted_usage > 0 and avg_usage > 0 and predicted_usage > avg_usage:
        saving_pct = ((predicted_usage - avg_usage) / predicted_usage) * 100.0
        if predicted_monthly_bill is not None:
            saving_estimate_dollars = predicted_monthly_bill * (saving_pct / 100.0)

    # Environmental trend
    predicted_co2 = (predicted_usage * 0.4) if predicted_usage is not None else None
    avg_co2 = avg_usage * 0.4 if avg_usage is not None else None

    env_trend = 'stable'
    env_pct_change = 0.0
    if predicted_co2 is not None and avg_co2 is not None and avg_co2 > 0:
        diff = predicted_co2 - avg_co2
        env_pct_change = (diff / avg_co2) * 100.0
        if env_pct_change > 2:
            env_trend = 'increasing'
        elif env_pct_change < -2:
            env_trend = 'decreasing'
        else:
            env_trend = 'stable'

    return {
        'peak_hour': peak_hour,
        'peak_period': peak_period,
        'peak_hour_avg': peak_hour_avg,
        'spike_count': spike_count,
        'spike_rate_per_1000': round(spike_rate_per_1000, 2),
        'appliance_message': appliance_message,
        'saving_pct': round(saving_pct, 2),
        'saving_estimate_dollars': round(saving_estimate_dollars, 2),
        'predicted_usage': predicted_usage,
        'avg_usage': round(avg_usage, 2),
        'env_trend': env_trend,
        'env_pct_change': round(env_pct_change, 2)
    }


@app.post('/api/upload/validate')
async def upload_validate(file: UploadFile = File(...)):
    """Validate an uploaded CSV and return a preview and suggested column mapping without saving it to disk.

    This routine attempts to detect CSV dialects (delimiter, header presence) and falls back to common encodings.
    """
    try:
        import io, csv
        contents = await file.read()
        sample_bytes = contents[:65536]
        text = sample_bytes.decode('utf-8', errors='replace')

        # Try to detect delimiter/header using csv.Sniffer
        try:
            dialect = csv.Sniffer().sniff(text)
            has_header = csv.Sniffer().has_header(text)
            sep = dialect.delimiter
        except Exception:
            # fallback: pandas autodetect by passing sep=None/engine='python'
            sep = None
            has_header = True

        # Fast attempt: let pandas autodetect delimiter (sep=None) using python engine
        try:
            sample = pd.read_csv(io.BytesIO(contents), nrows=10, sep=None, engine='python', encoding='utf-8', on_bad_lines='skip')
        except Exception:
            # Fallback: try a few alternatives (comma, semicolon, tab)
            read_attempts = [
                {'sep': ',', 'engine': 'c'},
                {'sep': ';', 'engine': 'python'},
                {'sep': '\t', 'engine': 'python'}
            ]
            sample = None
            for opts in read_attempts:
                try:
                    sample = pd.read_csv(io.BytesIO(contents), nrows=10, sep=opts['sep'], engine=opts['engine'], encoding='utf-8', on_bad_lines='skip')
                    break
                except Exception:
                    continue

            if sample is None:
                # try latin1 as last resort
                try:
                    sample = pd.read_csv(io.BytesIO(contents), nrows=10, sep=None, engine='python', encoding='latin1', on_bad_lines='skip')
                except Exception as e:
                    return JSONResponse(status_code=400, content={"message": f"Validation failed: could not parse sample CSV ({str(e)})"})

        suggested = suggest_mappings_from_sample(sample)

        preview = sample.head(5).fillna('').to_dict(orient='records')
        return {
            'preview': preview,
            'columns': list(sample.columns),
            'suggested': suggested
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": f"Validation failed: {str(e)}"})
# This is required for deployment (Render)
if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)