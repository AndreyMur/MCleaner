import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Packages from "./pages/Packages";
import Cleaner from "./pages/Cleaner";
import { JournalProvider } from "./context/JournalContext";
import { ToastProvider } from "./context/ToastContext";
import { ThemeProvider } from "./context/ThemeContext";
import ToastContainer from "./components/ToastContainer";

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
      <JournalProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="packages" element={<Packages />} />
              <Route path="cleaner" element={<Cleaner />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <ToastContainer />
      </JournalProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;
