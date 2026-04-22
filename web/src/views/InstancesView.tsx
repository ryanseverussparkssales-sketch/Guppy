import { Plus } from 'lucide-react'
import './InstancesView.css'

export default function InstancesView() {
  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Instances</h2>
        <button className="btn btn-primary">
          <Plus size={18} />
          New Instance
        </button>
      </div>

      <div className="empty-state">
        <h3>No instances yet</h3>
        <p>Create your first instance to get started with Guppy</p>
        <button className="btn btn-primary">Create Instance</button>
      </div>
    </div>
  )
}
