import { useRef, useState } from 'react'
import { Upload, X } from 'lucide-react'
import './FileUploadZone.css'

interface FileUploadZoneProps {
  onFilesSelected?: (files: File[]) => void
  maxSize?: number
  acceptedTypes?: string[]
}

export default function FileUploadZone({
  onFilesSelected,
  maxSize = 10 * 1024 * 1024, // 10MB
  acceptedTypes = ['*'],
}: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = Array.from(e.dataTransfer.files)
    processFiles(files)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files)
      processFiles(files)
    }
  }

  const processFiles = (files: File[]) => {
    const validFiles = files.filter((file) => {
      if (file.size > maxSize) {
        console.warn(`File ${file.name} exceeds size limit`)
        return false
      }

      if (acceptedTypes[0] !== '*' && !acceptedTypes.includes(file.type)) {
        console.warn(`File ${file.name} has unsupported type`)
        return false
      }

      return true
    })

    setSelectedFiles(validFiles)
    onFilesSelected?.(validFiles)
  }

  const removeFile = (index: number) => {
    const updated = selectedFiles.filter((_, i) => i !== index)
    setSelectedFiles(updated)
    onFilesSelected?.(updated)
  }

  return (
    <div className="file-upload-zone">
      <input
        ref={inputRef}
        type="file"
        multiple
        onChange={handleInputChange}
        className="file-input"
        accept={acceptedTypes.join(',')}
        style={{ display: 'none' }}
      />

      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <Upload size={32} className="upload-icon" />
        <p className="drop-text">Drag files here or click to upload</p>
        <small>Max {Math.floor(maxSize / 1024 / 1024)}MB per file</small>
      </div>

      {selectedFiles.length > 0 && (
        <div className="file-list">
          <h4>Selected Files ({selectedFiles.length})</h4>
          {selectedFiles.map((file, index) => (
            <div key={`${file.name}-${index}`} className="file-item">
              <span className="file-name">{file.name}</span>
              <span className="file-size">({(file.size / 1024).toFixed(1)}KB)</span>
              <button
                className="file-remove"
                onClick={() => removeFile(index)}
                title="Remove file"
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
