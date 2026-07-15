import { useState, useRef } from 'react';

export default function UploadPanel({ onUpload, isProcessing }) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleFile = (file) => {
    if (!file) return;
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg'];
    if (!validTypes.includes(file.type)) {
      alert('Please upload a PNG or JPG image.');
      return;
    }
    onUpload(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleClick = () => fileInputRef.current?.click();

  const handleChange = (e) => {
    const file = e.target.files[0];
    handleFile(file);
  };

  return (
    <div className="upload-overlay">
      <div
        className={`upload-box ${dragOver ? 'drag-over' : ''}`}
        onClick={handleClick}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".png,.jpg,.jpeg"
          onChange={handleChange}
        />
        {isProcessing ? (
          <>
            <div className="loading-spinner" style={{ marginBottom: 12 }} />
            <h2>Processing floor plan...</h2>
            <p>Detecting rooms using OpenCV</p>
          </>
        ) : (
          <>
            <h2>Upload Floor Plan</h2>
            <p>Drag and drop a PNG or JPG image, or click to browse</p>
            <button className="btn btn-primary">Choose File</button>
          </>
        )}
      </div>
    </div>
  );
}
