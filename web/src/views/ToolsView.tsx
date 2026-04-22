import './ToolsView.css'

export default function ToolsView() {
  return (
    <div className="view-container">
      <div className="view-header">
        <h2>Available Tools</h2>
      </div>
      <div className="tools-grid">
        <div className="tool-card">
          <h3>Web Search</h3>
          <p>Search the web for current information</p>
        </div>
        <div className="tool-card">
          <h3>Code Execution</h3>
          <p>Run and test code snippets</p>
        </div>
        <div className="tool-card">
          <h3>File Operations</h3>
          <p>Read and write files</p>
        </div>
        <div className="tool-card">
          <h3>API Integration</h3>
          <p>Connect to external APIs</p>
        </div>
      </div>
    </div>
  )
}
