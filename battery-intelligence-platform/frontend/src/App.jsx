import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './LandingPage'
import Dashboard from './Dashboard'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={
          <div className="page-enter">
            <Dashboard />
          </div>
        } />
      </Routes>
    </BrowserRouter>
  )
}

export default App
