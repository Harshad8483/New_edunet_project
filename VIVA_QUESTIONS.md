# Viva Questions & Answers
## AI-Based Smart Electricity Analyzer

### Project Overview
**Q: What is the main objective of this project?**
A: The main objective is to analyze electricity consumption patterns using AI to predict future usage, calculate estimated bills, and provide actionable insights to reduce carbon footprint and costs.

**Q: What technologies did you use?**
A:
- **Frontend**: React.js with Vite for high performance, Tailwind CSS for styling, and Framer Motion for animations.
- **Backend**: FastAPI (Python) for handling API requests and serving the ML model.
- **Machine Learning**: Scikit-learn (Linear Regression) for usage prediction.
- **Data Processing**: Pandas and NumPy for handling CSV datasets.

---

### Technical Questions

**Q: How does the prediction model work?**
A: We use a **Linear Regression** model trained on historical usage data. It takes the previous reading as input and predicts the next probable consumption value. We use `scikit-learn` to load the pre-trained `.pkl` model.

**Q: How is the "Green Score" calculated?**
A: The Green Score is a heuristic metric (0-100).
1. We calculate the **average usage** from the dataset.
2. We compare the **predicted usage** against this average.
3. If the predicted usage is *lower* than average, the score increases (efficiency).
4. If it's *higher*, the score decreases.
   - *Formula*: `Base Score (70) + (Improvement % * Factor)`

**Q: Why did you choose FastAPI over Flask or Django?**
A: FastAPI is significantly faster due to its asynchronous support (`async/await`) and automatic data validation using Pydantic models. It generates interactive API documentation (Swagger UI) automatically, which speeds up development.

**Q: Explain the data flow when a user uploads a file.**
1. User selects a CSV file in the React frontend.
2. Frontend sends it via a `POST` request to `/api/upload`.
3. Backend reads the file stream using `pandas`.
4. It normalizes column names (e.g., converts 'Timestamp' to 'date').
5. The processed data is saved to `electricity_data.csv`.
6. The global `data_store` variable is updated, and the new stats are returned to the frontend.

**Q: How do you handle Cross-Origin Resource Sharing (CORS)?**
A: Since the frontend runs on port 5173 and backend on 8000, we configured `CORSMiddleware` in FastAPI to allow requests specifically from `http://localhost:5173`.

---

### UI/UX Questions

**Q: What is "Glassmorphism" in your UI?**
A: It's a design trend used in our cards and panels. It uses a semi-transparent background (`bg-slate-800/40`) with a backdrop blur filter (`backdrop-blur-md`) to mimic the look of frosted glass, giving the app a modern, premium feel.

**Q: Why use Tailwind CSS instead of normal CSS?**
A: Tailwind provides utility classes that speed up development and ensure consistency. It also generates a very small CSS bundle by removing unused styles during the build process.

---

### Future Enhancements

**Q: How can you improve the prediction accuracy?**
A: We could upgrade to more advanced models like **LSTM (Long Short-Term Memory)** networks for time-series forecasting, which capture long-term dependencies better than simple regression.

**Q: How would you deploy this?**
A:
- **Frontend**: Deploy to Vercel or Netlify.
- **Backend**: Deploy to Render, Railway, or AWS EC2 (using Gunicorn/Uvicorn).
