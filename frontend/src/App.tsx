// src/App.tsx
import { Routes, Route, Navigate } from "react-router-dom";
import InputPage from "./pages/InputPage";
import ResultsPage from "./pages/ResultsPage";

function App() {
  return (
    <div className="app-root">
      <div className="app-shell">
        <Routes>
          <Route path="/" element={<InputPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default App;
