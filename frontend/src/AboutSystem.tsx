import './about-system.css'

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
        <span className="about-system-version">Version 1.0.0</span>
      </div>

      <div className="about-system-grid">
        <article className="about-system-card about-system-card-primary">
          <span className="about-system-card-label">DEVELOPED BY</span>
          <h2>Fan Avar Sanat Madain Engineering Co.</h2>
          <p>
            This Steelmaking Level 2 System was developed by Fan Avar Sanat Madain Engineering Co.
            for industrial production monitoring, process visibility, and Level 1 / Level 2 integration.
          </p>
        </article>

        <article className="about-system-card">
          <span className="about-system-card-label">SOFTWARE DEVELOPMENT</span>
          <h2>Amir Behvandi</h2>
          <p className="about-system-role">Software Developer / Industrial AI Engineer</p>
          <p>
            Software implementation and application development for the Steelmaking Level 2 platform.
          </p>
        </article>
      </div>

      <article className="about-system-card about-system-details">
        <div>
          <span>Product</span>
          <strong>Steelmaking Level 2 Platform</strong>
        </div>
        <div>
          <span>Plant</span>
          <strong>Mianeh Steel Complex</strong>
        </div>
        <div>
          <span>System Layer</span>
          <strong>Level 2 Manufacturing Operations</strong>
        </div>
        <div>
          <span>Application Type</span>
          <strong>Industrial Web Platform</strong>
        </div>
      </article>

      <footer className="about-system-footer">
        <span>© Fan Avar Sanat Madain Engineering Co. All rights reserved.</span>
        <span>Steelmaking Level 2 Operations Platform</span>
      </footer>
    </section>
  )
}
