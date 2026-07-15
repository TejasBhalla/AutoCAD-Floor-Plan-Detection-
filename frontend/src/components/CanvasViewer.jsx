import { useRef, useState, useEffect, useCallback } from 'react';
import { Stage, Layer, Image as KonvaImage, Line, Circle, Group, Text } from 'react-konva';
import Toolbar from './Toolbar';

const ROOM_COLORS = [
  { fill: 'rgba(59, 130, 246, 0.25)',  stroke: '#3b82f6', selected: 'rgba(59, 130, 246, 0.45)' },
  { fill: 'rgba(16, 185, 129, 0.25)',  stroke: '#10b981', selected: 'rgba(16, 185, 129, 0.45)' },
  { fill: 'rgba(245, 158, 11, 0.25)',  stroke: '#f59e0b', selected: 'rgba(245, 158, 11, 0.45)' },
  { fill: 'rgba(239, 68, 68, 0.25)',   stroke: '#ef4444', selected: 'rgba(239, 68, 68, 0.45)' },
  { fill: 'rgba(139, 92, 246, 0.25)',  stroke: '#8b5cf6', selected: 'rgba(139, 92, 246, 0.45)' },
  { fill: 'rgba(236, 72, 153, 0.25)',  stroke: '#ec4899', selected: 'rgba(236, 72, 153, 0.45)' },
  { fill: 'rgba(20, 184, 166, 0.25)',  stroke: '#14b8a6', selected: 'rgba(20, 184, 166, 0.45)' },
  { fill: 'rgba(249, 115, 22, 0.25)',  stroke: '#f97316', selected: 'rgba(249, 115, 22, 0.45)' },
  { fill: 'rgba(99, 102, 241, 0.25)',  stroke: '#6366f1', selected: 'rgba(99, 102, 241, 0.45)' },
  { fill: 'rgba(34, 197, 94, 0.25)',   stroke: '#22c55e', selected: 'rgba(34, 197, 94, 0.45)' },
  { fill: 'rgba(168, 85, 247, 0.25)',  stroke: '#a855f7', selected: 'rgba(168, 85, 247, 0.45)' },
  { fill: 'rgba(251, 146, 60, 0.25)',  stroke: '#fb923c', selected: 'rgba(251, 146, 60, 0.45)' },
];
const ROOM_STROKE_WIDTH = 2;
const VERTEX_FILL = '#2563eb';
const VERTEX_RADIUS = 6;
const LABEL_OFFSET = 0;

export function getRoomColor(roomIndex) {
  return ROOM_COLORS[roomIndex % ROOM_COLORS.length];
}

function getPolygonCenter(polygon) {
  const n = polygon.length;
  const cx = polygon.reduce((s, p) => s + p[0], 0) / n;
  const cy = polygon.reduce((s, p) => s + p[1], 0) / n;
  return { cx, cy };
}

export default function CanvasViewer({
  rooms,
  selectedRoomId,
  imageUrl,
  imageWidth,
  imageHeight,
  onSelectRoom,
  onUpdateVertex,
  onAddPolygon,
}) {
  const containerRef = useRef(null);
  const stageRef = useRef(null);
  const imageRef = useRef(null);
  const [konvaImage, setKonvaImage] = useState(null);
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 });
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 });
  const [stageScale, setStageScale] = useState(1);
  const [draggingVertex, setDraggingVertex] = useState(null);
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0, stageX: 0, stageY: 0 });

  // Load the floor plan image into a Konva-compatible Image
  useEffect(() => {
    if (!imageUrl) return;
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      setKonvaImage(img);
      // Fit image to container on load
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const scaleX = rect.width / img.width;
        const scaleY = rect.height / img.height;
        const fitScale = Math.min(scaleX, scaleY, 1) * 0.9;
        setStageScale(fitScale);
        setStagePos({
          x: (rect.width - img.width * fitScale) / 2,
          y: (rect.height - img.height * fitScale) / 2,
        });
      }
    };
    img.src = imageUrl;
  }, [imageUrl]);

  // Track container size
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setContainerSize({ width, height });
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Zoom with mouse wheel
  const handleWheel = useCallback((e) => {
    e.evt.preventDefault();
    const stage = stageRef.current;
    if (!stage) return;

    const oldScale = stageScale;
    const pointer = stage.getPointerPosition();

    const mousePointTo = {
      x: (pointer.x - stagePos.x) / oldScale,
      y: (pointer.y - stagePos.y) / oldScale,
    };

    const direction = e.evt.deltaY < 0 ? 1 : -1;
    const factor = 1.1;
    const newScale = direction > 0 ? oldScale * factor : oldScale / factor;
    const clampedScale = Math.max(0.1, Math.min(10, newScale));

    setStageScale(clampedScale);
    setStagePos({
      x: pointer.x - mousePointTo.x * clampedScale,
      y: pointer.y - mousePointTo.y * clampedScale,
    });
  }, [stageScale, stagePos]);

  // Pan with middle-click or when no vertex is being dragged
  const handleStageMouseDown = (e) => {
    const clickedOnEmpty = e.target === e.target.getStage() || e.target.name() === 'background-image';
    if (clickedOnEmpty) {
      // Check for middle mouse button or shift+click for panning
      if (e.evt.button === 1 || (e.evt.button === 0 && e.evt.shiftKey)) {
        setIsPanning(true);
        panStartRef.current = {
          x: e.evt.clientX,
          y: e.evt.clientY,
          stageX: stagePos.x,
          stageY: stagePos.y,
        };
        return;
      }
      onSelectRoom(null);
    }
  };

  const handleStageMouseMove = (e) => {
    if (isPanning) {
      const dx = e.evt.clientX - panStartRef.current.x;
      const dy = e.evt.clientY - panStartRef.current.y;
      setStagePos({
        x: panStartRef.current.stageX + dx,
        y: panStartRef.current.stageY + dy,
      });
    }
  };

  const handleStageMouseUp = () => {
    setIsPanning(false);
  };

  // Vertex drag handlers
  const handleVertexDragStart = (roomId, vertexIndex) => {
    setDraggingVertex({ roomId, vertexIndex });
  };

  const handleVertexDrag = (roomId, vertexIndex, e) => {
    const stage = stageRef.current;
    const pointer = stage.getPointerPosition();
    const x = (pointer.x - stagePos.x) / stageScale;
    const y = (pointer.y - stagePos.y) / stageScale;
    onUpdateVertex(roomId, vertexIndex, [Math.round(x), Math.round(y)]);
  };

  const handleVertexDragEnd = () => {
    setDraggingVertex(null);
  };

  // Zoom controls
  const zoomIn = () => {
    setStageScale((s) => Math.min(10, s * 1.2));
  };

  const zoomOut = () => {
    setStageScale((s) => Math.max(0.1, s / 1.2));
  };

  const resetView = () => {
    if (!konvaImage || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const scaleX = rect.width / konvaImage.width;
    const scaleY = rect.height / konvaImage.height;
    const fitScale = Math.min(scaleX, scaleY, 1) * 0.9;
    setStageScale(fitScale);
    setStagePos({
      x: (rect.width - konvaImage.width * fitScale) / 2,
      y: (rect.height - konvaImage.height * fitScale) / 2,
    });
  };

  return (
    <div className="canvas-area" ref={containerRef}>
      <Toolbar
        zoom={stageScale}
        onZoomIn={zoomIn}
        onZoomOut={zoomOut}
        onResetView={resetView}
        onAddPolygon={onAddPolygon}
      />

      <Stage
        ref={stageRef}
        width={containerSize.width}
        height={containerSize.height}
        x={stagePos.x}
        y={stagePos.y}
        scaleX={stageScale}
        scaleY={stageScale}
        onWheel={handleWheel}
        onMouseDown={handleStageMouseDown}
        onMouseMove={handleStageMouseMove}
        onMouseUp={handleStageMouseUp}
        draggable={false}
        style={{ cursor: isPanning ? 'grabbing' : 'default' }}
      >
        <Layer>
          {/* Background floor plan image */}
          {konvaImage && (
            <KonvaImage
              image={konvaImage}
              width={imageWidth}
              height={imageHeight}
              name="background-image"
            />
          )}

          {/* Room polygons */}
          {rooms.map((room, roomIndex) => {
            const isSelected = selectedRoomId === room.id;
            const colors = getRoomColor(roomIndex);
            const flatPoints = room.polygon.flat();
            const { cx, cy } = getPolygonCenter(room.polygon);

            return (
              <Group key={room.id}>
                {/* Filled polygon */}
                <Line
                  points={flatPoints}
                  fill={isSelected ? colors.selected : colors.fill}
                  closed
                  stroke={isSelected ? colors.stroke : colors.stroke}
                  strokeWidth={isSelected ? ROOM_STROKE_WIDTH + 1 : ROOM_STROKE_WIDTH}
                  onClick={() => onSelectRoom(room.id)}
                  onTap={() => onSelectRoom(room.id)}
                  hitStrokeWidth={12}
                  tension={0}
                  lineJoin="round"
                />

                {/* Room label */}
                <Text
                  x={cx}
                  y={cy}
                  text={room.name}
                  fontSize={14}
                  fontFamily="sans-serif"
                  fill="#1e293b"
                  align="center"
                  verticalAlign="middle"
                  offsetX={room.name.length * 3.5}
                  offsetY={7}
                  pointerEvents="none"
                />

                {/* Editable vertex handles — only visible when room is selected */}
                {isSelected && room.polygon.map((point, idx) => (
                  <Circle
                    key={`${room.id}-v-${idx}`}
                    x={point[0]}
                    y={point[1]}
                    radius={VERTEX_RADIUS}
                    fill={VERTEX_FILL}
                    stroke="white"
                    strokeWidth={2}
                    draggable
                    onDragStart={() => handleVertexDragStart(room.id, idx)}
                    onDragMove={(e) => handleVertexDrag(room.id, idx, e)}
                    onDragEnd={handleVertexDragEnd}
                    onMouseEnter={(e) => {
                      e.target.radius(VERTEX_RADIUS + 2);
                      e.target.getLayer().batchDraw();
                    }}
                    onMouseLeave={(e) => {
                      e.target.radius(VERTEX_RADIUS);
                      e.target.getLayer().batchDraw();
                    }}
                  />
                ))}
              </Group>
            );
          })}
        </Layer>
      </Stage>

      <div className="zoom-info">{Math.round(stageScale * 100)}%</div>
    </div>
  );
}
