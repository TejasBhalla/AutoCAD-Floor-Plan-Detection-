import { useState, useCallback } from 'react';
import UploadPanel from './components/UploadPanel';
import CanvasViewer from './components/CanvasViewer';
import RoomEditor from './components/RoomEditor';
import { uploadFloorPlan, saveLayout } from './services/api';

let nextId = 1000;

export default function App() {
  const [rooms, setRooms] = useState([]);
  const [selectedRoomId, setSelectedRoomId] = useState(null);
  const [imageUrl, setImageUrl] = useState(null);
  const [imageWidth, setImageWidth] = useState(0);
  const [imageHeight, setImageHeight] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [hasImage, setHasImage] = useState(false);
  const [saving, setSaving] = useState(false);

  const selectedRoom = rooms.find((r) => r.id === selectedRoomId) || null;

  const handleUpload = useCallback(async (file) => {
    setIsProcessing(true);
    try {
      const result = await uploadFloorPlan(file);
      setRooms(result.rooms);
      setImageWidth(result.image_width);
      setImageHeight(result.image_height);
      setImageUrl(result.image_url);
      setHasImage(true);
      setSelectedRoomId(null);

      // Assign nextId to avoid collisions
      if (result.rooms.length > 0) {
        nextId = Math.max(...result.rooms.map((r) => r.id)) + 1;
      }
    } catch (err) {
      console.error('Upload failed:', err);
      const msg = err.response?.data?.error || err.message || 'Upload failed';
      alert(`Upload failed: ${msg}`);
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const handleSelectRoom = useCallback((id) => {
    setSelectedRoomId(id);
  }, []);

  const handleUpdateName = useCallback((id, name) => {
    setRooms((prev) => prev.map((r) => (r.id === id ? { ...r, name } : r)));
  }, []);

  const handleUpdateVertex = useCallback((roomId, vertexIndex, newPos) => {
    setRooms((prev) =>
      prev.map((r) => {
        if (r.id !== roomId) return r;
        const polygon = [...r.polygon];
        polygon[vertexIndex] = newPos;
        return { ...r, polygon };
      })
    );
  }, []);

  const handleDeleteRoom = useCallback(
    (id) => {
      setRooms((prev) => prev.filter((r) => r.id !== id));
      if (selectedRoomId === id) {
        setSelectedRoomId(null);
      }
    },
    [selectedRoomId]
  );

  const handleAddPolygon = useCallback(() => {
    // Add a default rectangular room near the center of the image
    const cx = imageWidth / 2;
    const cy = imageHeight / 2;
    const size = 100;
    const newRoom = {
      id: nextId++,
      name: `Room ${nextId - 1}`,
      polygon: [
        [cx - size, cy - size],
        [cx + size, cy - size],
        [cx + size, cy + size],
        [cx - size, cy + size],
      ],
    };
    setRooms((prev) => [...prev, newRoom]);
    setSelectedRoomId(newRoom.id);
  }, [imageWidth, imageHeight]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await saveLayout(rooms);
      alert('Layout saved successfully!');
    } catch (err) {
      console.error('Save failed:', err);
      const msg = err.response?.data?.error || err.message || 'Save failed';
      alert(`Save failed: ${msg}`);
    } finally {
      setSaving(false);
    }
  }, [rooms]);

  return (
    <div className="app-container">
      <header className="header">
        <h1>Floor Plan Parser</h1>
        <div className="header-stats">
          <span>Detected Rooms: {rooms.length}</span>
          {saving && <span>Saving...</span>}
        </div>
      </header>

      <div className="main-content">
        {!hasImage ? (
          <div className="canvas-area">
            <UploadPanel onUpload={handleUpload} isProcessing={isProcessing} />
          </div>
        ) : (
          <>
            <CanvasViewer
              rooms={rooms}
              selectedRoomId={selectedRoomId}
              imageUrl={imageUrl}
              imageWidth={imageWidth}
              imageHeight={imageHeight}
              onSelectRoom={handleSelectRoom}
              onUpdateVertex={handleUpdateVertex}
              onAddPolygon={handleAddPolygon}
            />
            <RoomEditor
              room={selectedRoom}
              rooms={rooms}
              onUpdateName={handleUpdateName}
              onDeleteRoom={handleDeleteRoom}
              onSelectRoom={handleSelectRoom}
              onSave={handleSave}
              onAddPolygon={handleAddPolygon}
            />
          </>
        )}
      </div>
    </div>
  );
}
