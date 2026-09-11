import { useEffect, useRef, useState } from "react";
import {
  createViewer,
  flyToBounds,
  toCartographicDegrees,
  setBasemap,
  setLightingEnabled,
  BASEMAPS,
  type BasemapMode,
} from "../services/mapProvider";

interface Props {
  features: any[]; // GeoJSON features from result.location
  footprintBounds: number[] | null; // [west, south, east, north] of the AOI
  drawMode: boolean;
  onAoiDrawn: (geojson: Record<string, any>) => void;
  activeLayerKey: string | null; // e.g. "2025-06-01" — timeline sync (FR-15)
  layerDates: string[];
}

const CHANGE_COLORS: Record<string, string> = {
  vegetation_loss: "#f97316",
  vegetation_gain: "#22c55e",
  water_loss: "#eab308",
  water_gain: "#3b82f6",
  detection: "#e879f9",
};
const DEFAULT_COLOR = "#38bdf8";

function colorFor(feature: any): string {
  const p = feature.properties ?? {};
  return (
    CHANGE_COLORS[p.change_class] ??
    CHANGE_COLORS[p.kind] ??
    DEFAULT_COLOR
  );
}

export function CesiumGlobe({
  features, footprintBounds, drawMode, onAoiDrawn, activeLayerKey, layerDates,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const handlerRef = useRef<any>(null);
  const drawPtsRef = useRef<{ lon: number; lat: number }[]>([]);
  const [drawing, setDrawing] = useState(false);
  const [currentBasemap, setCurrentBasemap] = useState<BasemapMode>("satellite");
  const [sunLighting, setSunLighting] = useState(true);


  // init / destroy viewer
  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;
    const viewer = createViewer(containerRef.current);
    viewerRef.current = viewer;
    return () => {
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // fly to footprint when set
  useEffect(() => {
    if (viewerRef.current && footprintBounds && footprintBounds.length === 4) {
      flyToBounds(viewerRef.current, footprintBounds);
    }
  }, [footprintBounds]);

  // render result features as entities
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.entities.removeAll();
    for (const f of features.slice(0, 500)) {
      const Cesium = window.Cesium;
      const color = Cesium.Color.fromCssColorString(colorFor(f)).withAlpha(0.45);
      const outline = Cesium.Color.fromCssColorString(colorFor(f));
      const geom = f.geometry;
      if (!geom) continue;
      if (geom.type === "Polygon") {
        const rings = geom.coordinates as number[][][];
        const hierarchy = rings[0].map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat));
        viewer.entities.add({
          polygon: { hierarchy: new Cesium.PolygonHierarchy(hierarchy), material: color },
          polyline: { positions: [...hierarchy, hierarchy[0]], width: 2, material: outline },
        });
      } else if (geom.type === "MultiPolygon") {
        for (const poly of geom.coordinates as number[][][][]) {
          const hierarchy = poly[0].map(([lon, lat]) =>
            Cesium.Cartesian3.fromDegrees(lon, lat));
          viewer.entities.add({
            polygon: { hierarchy: new Cesium.PolygonHierarchy(hierarchy), material: color },
          });
        }
      }
    }
  }, [features]);

  // AOI drawing (FR-14 AC2): click vertices, double-click closes the polygon
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const Cesium = window.Cesium;
    handlerRef.current?.destroy();
    drawPtsRef.current = [];
    setDrawing(drawMode);

    if (!drawMode) return;
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handlerRef.current = handler;

    const tempEntity = viewer.entities.add({ polyline: { positions: [], width: 2 } });

    const updateLine = () => {
      const pts = drawPtsRef.current;
      const positions = pts.map((p) => Cesium.Cartesian3.fromDegrees(p.lon, p.lat));
      if (positions.length > 0 && drawMode) {
        tempEntity.polyline.positions =
          positions.length > 1 ? positions : [...positions, positions[0]];
      }
    };

    handler.setInputAction((click: any) => {
      const cartesian = viewer.camera.pickEllipsoid(
        click.position, viewer.scene.globe.ellipsoid);
      if (!cartesian) return;
      const { lon, lat } = toCartographicDegrees(cartesian);
      drawPtsRef.current.push({ lon, lat });
      updateLine();
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    handler.setInputAction(() => {
      const pts = drawPtsRef.current;
      if (pts.length >= 3) {
        const ring = [...pts.map((p) => [p.lon, p.lat]), [pts[0].lon, pts[0].lat]];
        onAoiDrawn({ type: "Polygon", coordinates: [ring] });
      }
      viewer.entities.remove(tempEntity);
      drawPtsRef.current = [];
      setDrawing(false);
    }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

    return () => {
      handler.destroy();
      handlerRef.current = null;
    };
  }, [drawMode, onAoiDrawn]);

  // timeline sync (FR-15): flash the active date layer label — per-date
  // raster layers themselves arrive via result features; here we only mark
  // which transition is active so parents can re-render layers.
  useEffect(() => {
    /* activeLayerKey consumed by parent to re-key features; no-op here */
  }, [activeLayerKey, layerDates]);

  const handleRecenter = () => {
    if (viewerRef.current && footprintBounds && footprintBounds.length === 4) {
      flyToBounds(viewerRef.current, footprintBounds);
    }
  };

  const handleBasemapChange = (mode: BasemapMode) => {
    setCurrentBasemap(mode);
    if (viewerRef.current) {
      setBasemap(viewerRef.current, mode);
    }
  };

  const handleToggleLighting = () => {
    const next = !sunLighting;
    setSunLighting(next);
    if (viewerRef.current) {
      setLightingEnabled(viewerRef.current, next);
    }
  };

  return (
    <div className="relative h-full w-full overflow-hidden bg-slate-950 select-none">
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />

      {/* Top-Left Floating HUD: Status, Recenter & Basemap Switcher */}
      <div className="absolute left-3 top-3 z-10 flex flex-col gap-2 pointer-events-auto">
        <div className="flex items-center gap-2 rounded-lg border border-slate-700/60 bg-slate-900/80 px-3 py-1.5 backdrop-blur-md shadow-lg shadow-black/40">
          <div className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-[11px] font-medium tracking-wide text-slate-200">
            3D Photorealistic Earth
          </span>
          {footprintBounds && (
            <button
              onClick={handleRecenter}
              title="Fly camera to satellite scene bounds"
              className="ml-2 flex items-center gap-1 rounded bg-sky-600/80 hover:bg-sky-500 px-2 py-0.5 text-[10px] font-semibold text-white transition-all shadow"
            >
              <span>🎯 Re-center</span>
            </button>
          )}
        </div>

        {/* Photorealistic Basemap Selector Pills */}
        <div className="flex items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-900/85 p-1 backdrop-blur-md shadow-lg">
          {(Object.keys(BASEMAPS) as BasemapMode[]).map((mode) => {
            const bm = BASEMAPS[mode];
            const isActive = currentBasemap === mode;
            return (
              <button
                key={mode}
                onClick={() => handleBasemapChange(mode)}
                className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium transition-all ${
                  isActive
                    ? "bg-sky-600 text-white shadow-sm font-semibold"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <span>{bm.icon}</span>
                <span>{bm.name}</span>
              </button>
            );
          })}

          <div className="h-3 w-px bg-slate-700 mx-0.5" />

          {/* Sunlight / Day-Night Terminator Toggle */}
          <button
            onClick={handleToggleLighting}
            title="Toggle realistic dynamic sunlight and day/night terminator"
            className={`flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium transition-all ${
              sunLighting
                ? "bg-amber-600/30 text-amber-300 border border-amber-500/40"
                : "text-slate-400 hover:bg-slate-800"
            }`}
          >
            <span>☀️</span>
            <span>Sun: {sunLighting ? "ON" : "OFF"}</span>
          </button>
        </div>

        {drawMode && (
          <div className="animate-pulse rounded-lg border border-amber-500/50 bg-amber-950/80 px-3 py-2 text-xs text-amber-200 backdrop-blur-md shadow-xl">
            <div className="font-semibold flex items-center gap-1">
              <span>✏️ AOI Draw Mode Active</span>
            </div>
            <p className="text-[11px] text-amber-300/90 mt-0.5">
              Click on globe to place vertices. Double-click to close polygon.
            </p>
          </div>
        )}

        {!drawMode && drawing === false && layerDates.length > 1 && activeLayerKey && (
          <div className="rounded-lg border border-slate-700/60 bg-slate-900/80 px-3 py-1 text-xs text-sky-300 backdrop-blur-md">
            Active Temporal Layer: <span className="font-mono text-white font-semibold">{activeLayerKey}</span>
          </div>
        )}
      </div>

      {/* Top-Right Floating HUD: Change Detection & Feature Legend */}
      <div className="absolute right-3 top-3 z-10 pointer-events-auto">
        <div className="rounded-lg border border-slate-700/60 bg-slate-900/85 p-2.5 backdrop-blur-md shadow-xl text-xs space-y-1.5 max-w-[200px]">
          <div className="flex items-center justify-between border-b border-slate-800 pb-1 text-[10px] uppercase font-bold tracking-wider text-slate-400">
            <span>Visual Legend</span>
            <span className="text-sky-400 font-mono">{features.length} hits</span>
          </div>
          <div className="space-y-1 text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-sm bg-[#f97316] ring-1 ring-orange-300/40" />
              <span className="text-slate-300">Vegetation Loss</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-sm bg-[#22c55e] ring-1 ring-emerald-300/40" />
              <span className="text-slate-300">Vegetation Gain</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-sm bg-[#3b82f6] ring-1 ring-blue-300/40" />
              <span className="text-slate-300">Water Shift / Flood</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-sm bg-[#e879f9] ring-1 ring-pink-300/40" />
              <span className="text-slate-300">DINO Zero-Shot Target</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
