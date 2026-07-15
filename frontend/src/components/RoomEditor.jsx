import { useState, useEffect } from 'react';

export default function RoomEditor({ room, rooms, onUpdateName, onDeleteRoom, onSelectRoom, onSave, onAddPolygon }) {
  const [editName, setEditName] = useState('');

  useEffect(() => {
    if (room) {
      setEditName(room.name);
    }
  }, [room]);

  const handleNameChange = (e) => {
    setEditName(e.target.value);
  };

  const handleNameBlur = () => {
    if (room && editName.trim()) {
      onUpdateName(room.id, editName.trim());
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.target.blur();
    }
  };

  return (
    <div className="sidebar">
      <h2>Room Editor</h2>

      <div className="sidebar-section">
        <div className="btn-group" style={{ marginBottom: 12 }}>
          <button className="btn btn-success" onClick={onSave} style={{ flex: 1 }}>
            Save Layout
          </button>
          <button className="btn btn-primary" onClick={onAddPolygon} style={{ flex: 1 }}>
            + Add Room
          </button>
        </div>
      </div>

      {room && (
        <div className="sidebar-section">
          <label>Selected Room</label>
          <input
            type="text"
            value={editName}
            onChange={handleNameChange}
            onBlur={handleNameBlur}
            onKeyDown={handleKeyDown}
            placeholder="Room name"
          />
          <div style={{ marginTop: 12 }}>
            <label>Vertices: {room.polygon.length}</label>
          </div>
          <button
            className="btn btn-danger"
            style={{ marginTop: 12, width: '100%' }}
            onClick={() => onDeleteRoom(room.id)}
          >
            Delete Room
          </button>
        </div>
      )}

      <div className="sidebar-section" style={{ flex: 1, overflow: 'auto' }}>
        <label>All Rooms ({rooms.length})</label>
        <ul className="room-list">
          {rooms.map((r) => (
            <li
              key={r.id}
              className={room && room.id === r.id ? 'selected' : ''}
              onClick={() => onSelectRoom(r.id)}
            >
              <span className="room-label">
                <span className="room-swatch" />
                {r.name}
              </span>
              <button
                className="delete-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteRoom(r.id);
                }}
                title="Delete room"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
