import { Volume2 } from 'lucide-react'
import './VoicesView.css'

export default function VoicesView() {
  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Voice Settings</h2>
      </div>
      <div className="voice-config">
        <div className="config-section">
          <h3>Text-to-Speech (TTS)</h3>
          <div className="config-item">
            <label>Provider:</label>
            <select>
              <option>Kokoro (Fast)</option>
              <option>ElevenLabs (Premium)</option>
              <option>System TTS</option>
            </select>
          </div>
          <div className="config-item">
            <label>Voice:</label>
            <select>
              <option>Default</option>
              <option>Male</option>
              <option>Female</option>
            </select>
          </div>
        </div>

        <div className="config-section">
          <h3>Speech-to-Text (STT)</h3>
          <div className="config-item">
            <label>Model Size:</label>
            <select>
              <option>Large (Most accurate)</option>
              <option>Medium</option>
              <option>Small (Fastest)</option>
            </select>
          </div>
        </div>

        <button className="btn btn-primary">
          <Volume2 size={18} />
          Test Audio
        </button>
      </div>
    </div>
  )
}
