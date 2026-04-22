import { Settings } from 'lucide-react'
import './ModelsView.css'

export default function ModelsView() {
  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Models & LLMs</h2>
        <button className="btn btn-primary">
          <Settings size={18} />
          Configure
        </button>
      </div>
      <div className="empty-state">
        <h3>No models configured</h3>
        <p>Set up your preferred AI models (local or cloud)</p>
        <button className="btn btn-primary">Add Model</button>
      </div>
    </div>
  )
}
