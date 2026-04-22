import { useState } from 'react'
import { Palette, Copy, Check } from 'lucide-react'
import { useTheme, THEME_PRESETS } from '../hooks/useTheme'
import './ThemeSettings.css'

export default function ThemeSettings() {
  const { theme, preset, customColors, resolvedTheme, setThemeMode, setThemePreset, availablePresets } = useTheme()
  const [copiedColor, setCopiedColor] = useState<string | null>(null)
  const [showColorPicker, setShowColorPicker] = useState(false)

  const handleColorCopy = (color: string) => {
    navigator.clipboard.writeText(color)
    setCopiedColor(color)
    setTimeout(() => setCopiedColor(null), 2000)
  }

  const currentColors = customColors[preset] || THEME_PRESETS[preset]?.[resolvedTheme]

  return (
    <div className="theme-settings-container">
      <div className="settings-header">
        <h2>Theme Settings</h2>
        <p>Customize the appearance of your interface</p>
      </div>

      <div className="theme-controls">
        <div className="control-section">
          <h3>Theme Mode</h3>
          <div className="theme-buttons">
            <button
              className={`theme-btn ${theme === 'light' ? 'active' : ''}`}
              onClick={() => setThemeMode('light')}
            >
              ☀️ Light
            </button>
            <button
              className={`theme-btn ${theme === 'dark' ? 'active' : ''}`}
              onClick={() => setThemeMode('dark')}
            >
              🌙 Dark
            </button>
            <button
              className={`theme-btn ${theme === 'auto' ? 'active' : ''}`}
              onClick={() => setThemeMode('auto')}
            >
              🔄 Auto
            </button>
          </div>
        </div>

        <div className="control-section">
          <h3>Color Preset</h3>
          <div className="preset-grid">
            {availablePresets.map((presetName) => (
              <button
                key={presetName}
                className={`preset-btn ${preset === presetName ? 'active' : ''}`}
                onClick={() => setThemePreset(presetName)}
                title={presetName}
              >
                <div className="preset-preview">
                  <div
                    className="preview-box"
                    style={{
                      backgroundColor: THEME_PRESETS[presetName][resolvedTheme].accent,
                    }}
                  />
                </div>
                <span>{presetName.charAt(0).toUpperCase() + presetName.slice(1)}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="control-section">
          <h3>Current Theme Colors</h3>
          {currentColors && (
            <div className="color-grid">
              {Object.entries(currentColors).map(([key, color]) => (
                <div key={key} className="color-item">
                  <div
                    className="color-preview"
                    style={{ backgroundColor: color }}
                    title={color}
                  />
                  <div className="color-info">
                    <p className="color-name">{key}</p>
                    <code className="color-value">{color}</code>
                  </div>
                  <button
                    className="color-copy-btn"
                    onClick={() => handleColorCopy(color)}
                    title="Copy hex code"
                  >
                    {copiedColor === color ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="control-section">
          <h3>Create Custom Theme</h3>
          <button
            className="btn btn-secondary"
            onClick={() => setShowColorPicker(!showColorPicker)}
          >
            <Palette size={18} />
            {showColorPicker ? 'Hide' : 'Show'} Color Picker
          </button>

          {showColorPicker && (
            <div className="custom-theme-form">
              <p>
                <small>
                  Use the developer tools to modify colors in real-time, then save your
                  custom theme.
                </small>
              </p>
              <div className="form-group">
                <label>Theme Name</label>
                <input
                  type="text"
                  placeholder="e.g., My Custom Theme"
                  className="input-field"
                />
              </div>
              <button className="btn btn-primary">Save Custom Theme</button>
            </div>
          )}
        </div>

        <div className="control-section">
          <h3>Preview</h3>
          <div className="theme-preview">
            <div className="preview-item">
              <button className="btn btn-primary">Primary Button</button>
            </div>
            <div className="preview-item">
              <button className="btn btn-secondary">Secondary Button</button>
            </div>
            <div className="preview-item">
              <input type="text" placeholder="Input field" className="input-field" />
            </div>
            <div className="preview-item">
              <span className="badge">Tag</span>
              <span className="badge">Theme</span>
              <span className="badge">Preview</span>
            </div>
          </div>
        </div>
      </div>

      <div className="theme-info">
        <h3>About Themes</h3>
        <ul>
          <li><strong>Light:</strong> Bright colors optimized for daylight</li>
          <li><strong>Dark:</strong> Dark colors optimized for low-light environments</li>
          <li><strong>Auto:</strong> Automatically follows system preference</li>
          <li><strong>Presets:</strong> Pre-configured color schemes from design libraries</li>
          <li><strong>Custom:</strong> Create and save your own color schemes</li>
        </ul>
      </div>
    </div>
  )
}
