import { Plus } from 'lucide-react'
import './LibraryView.css'

export default function LibraryView() {
  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Library</h2>
        <button className="btn btn-primary">
          <Plus size={18} />
          New Collection
        </button>
      </div>
      <div className="empty-state">
        <h3>Your library is empty</h3>
        <p>Save prompts, templates, and artifacts for quick access</p>
        <button className="btn btn-primary">Create Collection</button>
      </div>
    </div>
  )
}
