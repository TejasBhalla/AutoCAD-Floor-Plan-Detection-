export default function Toolbar({ zoom, onZoomIn, onZoomOut, onResetView, onAddPolygon }) {
  return (
    <div className="toolbar">
      <button className="btn btn-secondary" onClick={onZoomIn} title="Zoom In">+</button>
      <button className="btn btn-secondary" onClick={onZoomOut} title="Zoom Out">−</button>
      <button className="btn btn-secondary" onClick={onResetView} title="Reset View">⟲</button>
      <button className="btn btn-primary" onClick={onAddPolygon} title="Add Polygon">Add Room</button>
    </div>
  );
}
