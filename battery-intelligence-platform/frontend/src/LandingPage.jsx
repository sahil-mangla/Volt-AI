import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Zap, Activity, TrendingUp, Shield, Brain, Wifi, Wrench, Smartphone } from 'lucide-react'
import './LandingPage.css'

function LandingPage() {
  const navigate = useNavigate()
  const [exiting, setExiting] = useState(false)
  const sectionsRef = useRef([])

  // Scroll-triggered fade-in
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible')
          }
        })
      },
      { threshold: 0.15 }
    )

    sectionsRef.current.forEach((el) => {
      if (el) observer.observe(el)
    })

    return () => observer.disconnect()
  }, [])

  const handleEnterDashboard = () => {
    setExiting(true)
    setTimeout(() => {
      navigate('/dashboard')
    }, 500) // matches the CSS animation duration
  }

  return (
    <div className={`landing-page ${exiting ? 'page-exit' : ''}`}>
      {/* ===== NAVBAR ===== */}
      <nav className="flex items-center justify-between px-8 py-5 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <Zap className="h-9 w-9 text-blue-500 logo-pulse" />
          <span className="text-2xl font-bold text-white tracking-tight">VoltAI</span>
        </div>
        <button
          onClick={handleEnterDashboard}
          className="text-sm text-blue-400 hover:text-blue-300 transition-colors font-medium"
        >
          Go to Dashboard →
        </button>
      </nav>

      {/* ===== HERO SECTION ===== */}
      <section className="flex flex-col items-center justify-center text-center px-6 pt-20 pb-28 max-w-5xl mx-auto">
        <div
          className="fade-in-up visible"
        >
          <h1 className="text-5xl md:text-7xl font-extrabold leading-tight mb-8 hero-gradient-text">
            Predictive Intelligence
            <br />
            for Fleet Management
          </h1>
          <p className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-12 leading-relaxed">
            VoltAI harnesses the power of artificial intelligence to predict equipment failures,
            optimize maintenance schedules, and keep your fleet running at peak performance.
          </p>
          <button
            onClick={handleEnterDashboard}
            className="cta-button"
          >
            Enter Dashboard
          </button>
        </div>
      </section>

      {/* ===== FEATURES SECTION ===== */}
      <section
        ref={(el) => (sectionsRef.current[0] = el)}
        className="fade-in-up max-w-7xl mx-auto px-6 pb-24"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Real-Time Monitoring */}
          <div className="feature-card rounded-xl p-8">
            <div className="feature-icon w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Activity className="h-7 w-7 text-blue-400" />
            </div>
            <h3 className="text-xl font-bold text-white mb-3">Real-Time Monitoring</h3>
            <p className="text-gray-400 leading-relaxed">
              Track your entire fleet with live telemetry data and instant alerts for critical issues.
            </p>
          </div>

          {/* Card 2: Predictive Analytics */}
          <div className="feature-card rounded-xl p-8">
            <div className="feature-icon w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <TrendingUp className="h-7 w-7 text-blue-400" />
            </div>
            <h3 className="text-xl font-bold text-white mb-3">Predictive Analytics</h3>
            <p className="text-gray-400 leading-relaxed">
              AI-powered algorithms analyze degradation trends to forecast maintenance needs before failures occur.
            </p>
          </div>

          {/* Card 3: Reliability Optimization */}
          <div className="feature-card rounded-xl p-8">
            <div className="feature-icon w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Shield className="h-7 w-7 text-blue-400" />
            </div>
            <h3 className="text-xl font-bold text-white mb-3">Reliability Optimization</h3>
            <p className="text-gray-400 leading-relaxed">
              Maximize uptime and reduce costs by optimizing maintenance schedules based on actual equipment health.
            </p>
          </div>
        </div>
      </section>

      {/* ===== VISION SECTION ===== */}
      <section
        ref={(el) => (sectionsRef.current[1] = el)}
        className="fade-in-up max-w-5xl mx-auto px-6 pb-24"
      >
        <div className="vision-card p-10 md:p-14">
          <h2 className="text-3xl md:text-4xl font-bold text-white text-center mb-12">
            Our Vision for the Future
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Vision Item 1 */}
            <div className="flex items-start gap-4">
              <div className="vision-number text-white">1</div>
              <div>
                <h4 className="text-lg font-bold text-white mb-1">Advanced Machine Learning</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Implement deeper neural networks for more accurate failure predictions and anomaly detection.
                </p>
              </div>
            </div>

            {/* Vision Item 2 */}
            <div className="flex items-start gap-4">
              <div className="vision-number text-white">2</div>
              <div>
                <h4 className="text-lg font-bold text-white mb-1">IoT Integration</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Seamlessly connect with IoT sensors across diverse equipment types and manufacturers.
                </p>
              </div>
            </div>

            {/* Vision Item 3 */}
            <div className="flex items-start gap-4">
              <div className="vision-number text-white">3</div>
              <div>
                <h4 className="text-lg font-bold text-white mb-1">Automated Maintenance</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Enable automatic work order creation and resource allocation based on AI recommendations.
                </p>
              </div>
            </div>

            {/* Vision Item 4 */}
            <div className="flex items-start gap-4">
              <div className="vision-number text-white">4</div>
              <div>
                <h4 className="text-lg font-bold text-white mb-1">Mobile Experience</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Launch native mobile apps for on-the-go fleet monitoring and management.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="landing-footer py-8 text-center text-gray-500 text-sm">
        <p>© 2026 VoltAI — Predictive Intelligence for Smarter Fleets</p>
      </footer>
    </div>
  )
}

export default LandingPage
