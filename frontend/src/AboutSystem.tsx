import './about-system.css'
import { APP_VERSION } from './version'

export function AboutSystem() {
  return (
    <section className="about-system" aria-labelledby="about-system-title">
      <div className="about-system-hero">
        <div className="about-system-brand">
          <span className="about-system-logo">
            <img src="/mianeh-steel-logo.png" alt="Mianeh Steel Complex logo" />
          </span>
          <div>
            <span className="section-kicker">SYSTEM INFORMATION</span>
            <h1 id="about-system-title">About System</h1>
            <p>Steelmaking Level 2 Operations Platform</p>
          </div>
        </div>
        <span className="about-system-version">Version {APP_VERSION}</span>
      </div>

      <div className="about-system-grid">
        <article className="about-system-card about-system-card-primary">
          <span className="about-system-card-label">PROJECT & INDUSTRIAL PARTNERSHIP</span>
          <h2>Developed for Mianeh Steel Company</h2>
          <p>
            The Steelmaking Level 2 Platform is developed for Mianeh Steel Company in collaboration
            with MITE to support industrial production monitoring, process visibility, and Level 1 / Level 2 integration.
          </p>
        </article>

        <article className="about-system-card">
          <span className="about-system-card-label">TECHNOLOGY COLLABORATION</span>
          <h2>MITE</h2>
        </article>
      </div>

      <article className="about-system-card about-system-details">
        <div>
          <span>Product</span>
          <strong>Steelmaking Level 2 Platform</strong>
        </div>
        <div>
          <span>Client / Plant</span>
          <strong>Mianeh Steel Company</strong>
        </div>
        <div>
          <span>Technology Collaboration</span>
          <strong>MITE</strong>
        </div>
        <div>
          <span>Developer</span>
          <strong>Amir Behvandi</strong>
        </div>
      </article>

      <footer className="about-system-footer">
        <span>Developed for Mianeh Steel Company in collaboration with MITE.</span>
        <span>Developer: Amir Behvandi · Steelmaking Level 2 Platform</span>
      </footer>
    </section>
  )
}
