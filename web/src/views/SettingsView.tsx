import { Save } from 'lucide-react'
import './SettingsView.css'

export default function SettingsView() {
  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Settings</h2>
      </div>

      <div className="settings-grid">
        <div className="settings-section">
          <h3>API Configuration</h3>
          <div className="setting-item">
            <label>API Key</label>
            <input type="password" placeholder="Enter your API key" />
          </div>
          <div className="setting-item">
            <label>Model</label>
            <select>
              <option>Claude Sonnet 4</option>
              <option>Claude Haiku</option>
              <option>Local Model</option>
            </select>
          </div>
        </div>

        <div className="settings-section">
          <h3>Personalization</h3>
          <div className="setting-item">
            <label>
              <input type="checkbox" />
              Enable dark mode
            </label>
          </div>
          <div className="setting-item">
            <label>
              <input type="checkbox" />
              Send usage analytics
            </label>
          </div>
        </div>

        <div className="settings-section">
          <h3>Advanced</h3>
          <div className="setting-item">
            <label>Temperature</label>
            <input type="range" min="0" max="1" step="0.1" />
          </div>
          <div className="setting-item">
            <label>Max Tokens</label>
            <input type="number" placeholder="4096" />
          </div>
        </div>
      </div>

      <button className="btn btn-primary">
        <Save size={18} />
        Save Settings
      </button>
    </div>
  )
}
