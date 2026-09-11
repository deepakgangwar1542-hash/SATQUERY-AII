/**
 * GlobeWorkspace — THE VISUAL CENTERPIECE
 *
 * Renders the Cesium 3D photorealistic Earth.
 * Controls are deliberately minimal: three small icon buttons only.
 *
 *   [ Layers ]  [ Focus ]  [ Time ]
 *
 * Each opens a compact popover — NOT a permanent sidebar panel.
 * AOI draw mode shows a minimal indicator.
 * Result features render as glowing polygons with click-to-inspect.
 */
import { useEffect, useRef, useState, useCallback } from "react";
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
  features: any[];
  footprintBounds: number[] | null;
  drawMode: boolean;
  onAoiDrawn: (geojson: Record<string, any>) => void;
  layerDates: string[];
  showIdleOverlay?: boolean; // show the hero query composer overlay
}

const CHANGE_COLORS: Record<string, string> = {
  vegetation_loss: "#f97316",
  vegetation_gain: "#22c55e",
  water_loss: "#eab308",
  water_gain: "#3b82f6",
  detection: "#e879f9",
};

function colorFor(f: any): string {
  const p = f.properties ?? {};
  return CHANGE_COLORS[p.change_class] ?? CHANGE_COLORS[p.kind] ?? "#38bdf8";
}

type LayerFilter = "all" | "change" | "detections";

export function GlobeWorkspace({
  features,
  footprintBounds,
  drawMode,
  onAoiDrawn,
  layerDates,
  showIdleOverlay = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const handlerRef = useRef<any>(null);
  const drawPtsRef = useRef<{ lon: number; lat: number }[]>([]);

  const [basemap, setBasemapState] = useState<BasemapMode>("satellite");
  const [sunOn, setSunOn] = useState(true);
  const [activePopover, setActivePopover] = useState<null | "layers" | "focus" | "time">(null);
  const [layerFilter, setLayerFilter] = useState<LayerFilter>("all");
  const [entityInfo, setEntityInfo] = useState<{ title: string; category: string; } | null>(null);

  // Init viewer
  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;
    const viewer = createViewer(containerRef.current);
    viewerRef.current = viewer;

    // Entity click
    const ch = new (window.Cesium.ScreenSpaceEventHandler)(viewer.scene.canvas);
    ch.setInputAction((e: any) => {
      const p = viewer.scene.pick(e.position);
      if (window.Cesium.defined(p) && p.id?._satProps) {
        setEntityInfo(p.id._satProps);
      } else {
        setEntityInfo(null);
        setActivePopover(null);
      }
    }, window.Cesium.ScreenSpaceEventType.LEFT_CLICK);

    return () => { ch.destroy(); viewer.destroy(); viewerRef.current = null; };
  }, []);

  // Fly to footprint
  useEffect(() => {
    if (viewerRef.current && footprintBounds?.length === 4) {
      flyToBounds(viewerRef.current, footprintBounds);
    }
  }, [footprintBounds]);

  // Render features
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.entities.removeAll();

    const Cesium = window.Cesium;
    const filtered = features.filter((f) => {
      if (layerFilter === "all") return true;
      const isDet = (f.properties?.kind === "detection" || f.properties?.type === "detection");
      return layerFilter === "detections" ? isDet : !isDet;
    });

    for (const f of filtered.slice(0, 500)) {
      const hex = colorFor(f);
      const color = Cesium.Color.fromCssColorString(hex).withAlpha(0.45);
      const outline = Cesium.Color.fromCssColorString(hex);
      const geom = f.geometry;
      if (!geom) continue;

      const props = { title: f.properties?.label || f.properties?.change_class || "Feature", category: f.properties?.kind || "change" };

      if (geom.type === "Polygon") {
        const hier = geom.coordinates[0].map(([lon, lat]: number[]) => Cesium.Cartesian3.fromDegrees(lon, lat));
        const ent = viewer.entities.add({
          polygon: { hierarchy: new Cesium.PolygonHierarchy(hier), material: color, outline: true, outlineColor: outline },
          polyline: { positions: [...hier, hier[0]], width: 2, material: outline },
        });
        ent._satProps = props;
      } else if (geom.type === "MultiPolygon") {
        for (const poly of geom.coordinates as number[][][][]) {
          const hier = poly[0].map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat));
          viewer.entities.add({ polygon: { hierarchy: new Cesium.PolygonHierarchy(hier), material: color } });
        }
      } else if (geom.type === "Point") {
        const [lon, lat] = geom.coordinates as number[];
        viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(lon, lat),
          point: { pixelSize: 10, color: outline, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
        });
      }
    }
  }, [features, layerFilter]);

  // AOI drawing
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const Cesium = window.Cesium;
    handlerRef.current?.destroy();
    drawPtsRef.current = [];
    if (!drawMode) return;

    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handlerRef.current = handler;
    const tmpEnt = viewer.entities.add({ polyline: { positions: [], width: 2.5, material: Cesium.Color.YELLOW } });

    const updateLine = () => {
      const pts = drawPtsRef.current.map((p) => Cesium.Cartesian3.fromDegrees(p.lon, p.lat));
      if (pts.length > 0) tmpEnt.polyline.positions = pts.length > 1 ? pts : [...pts, pts[0]];
    };

    handler.setInputAction((click: any) => {
      const cart = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);
      if (!cart) return;
      const { lon, lat } = toCartographicDegrees(cart);
      drawPtsRef.current.push({ lon, lat });
      updateLine();
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    handler.setInputAction(() => {
      const pts = drawPtsRef.current;
      if (pts.length >= 3) {
        onAoiDrawn({ type: "Polygon", coordinates: [[...pts.map((p) => [p.lon, p.lat]), [pts[0].lon, pts[0].lat]]] });
      }
      viewer.entities.remove(tmpEnt);
      drawPtsRef.current = [];
    }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

    return () => { handler.destroy(); handlerRef.current = null; };
  }, [drawMode, onAoiDrawn]);

  const handleBasemap = useCallback((mode: BasemapMode) => {
    setBasemapState(mode);
    if (viewerRef.current) setBasemap(viewerRef.current, mode);
  }, []);

  const handleSun = useCallback(() => {
    setSunOn((v) => {
      if (viewerRef.current) setLightingEnabled(viewerRef.current, !v);
      return !v;
    });
  }, []);

  const handleFitScene = () => {
    if (viewerRef.current && footprintBounds?.length === 4) {
      flyToBounds(viewerRef.current, footprintBounds);
    }
    setActivePopover(null);
  };

  const togglePopover = (name: typeof activePopover) => {
    setActivePopover((v) => (v === name ? null : name));
  };

  return (
    <div className="relative h-full w-full overflow-hidden bg-slate-950">
      {/* Cesium Canvas */}
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />

      {/* AOI Draw Mode Banner */}
      {drawMode && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20 animate-pulse rounded-xl border border-amber-500/60 bg-amber-950/90 px-4 py-2 text-xs text-amber-200 backdrop-blur-md pointer-events-none shadow-lg">
          ✏️ AOI Draw Mode · Click to place vertices · Double-click to close
        </div>
      )}

      {/* Entity Info Popup (bottom left) */}
      {entityInfo && !showIdleOverlay && (
        <div className="absolute bottom-4 left-4 z-20 rounded-xl border border-sky-500/40 bg-slate-900/90 p-3 text-xs backdrop-blur-lg shadow-2xl max-w-[200px] animate-fade-in">
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="font-medium text-sky-300 truncate">{entityInfo.title}</span>
            <button onClick={() => setEntityInfo(null)} className="text-slate-400 hover:text-white shrink-0">✕</button>
          </div>
          <span className="text-slate-500 font-mono text-[10px]">{entityInfo.category}</span>
        </div>
      )}

      {/* ── Minimal HUD Toolbar (top-left) ── */}
      {!showIdleOverlay && (
        <div className="absolute left-3 top-3 z-20 flex items-center gap-2 pointer-events-auto">
          {/* Layers popover */}
          <div className="relative">
            <button
              onClick={() => togglePopover("layers")}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium backdrop-blur-xl shadow-lg transition-all ${
                activePopover === "layers"
                  ? "border-sky-500/60 bg-sky-950/90 text-sky-300"
                  : "border-slate-700/70 bg-slate-900/80 text-slate-300 hover:text-white hover:border-slate-500"
              }`}
            >
              <span>⚟</span>
              <span>Layers</span>
            </button>

            {activePopover === "layers" && (
              <div className="absolute top-full left-0 mt-2 w-52 rounded-xl border border-slate-700/70 bg-slate-900/95 p-3 backdrop-blur-xl shadow-2xl animate-slide-up">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-2.5">Basemap</p>
                {(Object.keys(BASEMAPS) as BasemapMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => handleBasemap(mode)}
                    className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-xs text-left transition-colors mb-0.5 ${
                      basemap === mode ? "bg-sky-600 text-white" : "text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    <span>{BASEMAPS[mode].icon}</span>
                    <span>{BASEMAPS[mode].name}</span>
                  </button>
                ))}

                <div className="border-t border-slate-700/50 mt-2.5 pt-2.5">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-2">Data Layers</p>
                  {features.length > 0 && (
                    <>
                      <button
                        onClick={() => setLayerFilter("all")}
                        className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-xs text-left transition-colors mb-0.5 ${
                          layerFilter === "all" ? "bg-indigo-700 text-white" : "text-slate-300 hover:bg-slate-800"
                        }`}
                      >
                        ☑ All Features ({features.length})
                      </button>
                      <button
                        onClick={() => setLayerFilter("change")}
                        className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-xs text-left transition-colors mb-0.5 ${
                          layerFilter === "change" ? "bg-orange-700 text-white" : "text-slate-300 hover:bg-slate-800"
                        }`}
                      >
                        ☑ Change Regions
                      </button>
                      <button
                        onClick={() => setLayerFilter("detections")}
                        className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-xs text-left transition-colors ${
                          layerFilter === "detections" ? "bg-fuchsia-700 text-white" : "text-slate-300 hover:bg-slate-800"
                        }`}
                      >
                        ☑ Detections Only
                      </button>
                    </>
                  )}
                  <button
                    onClick={handleSun}
                    className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-1.5 text-xs text-left transition-colors mt-0.5 ${
                      sunOn ? "bg-amber-700/40 text-amber-300" : "text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    ☀️ Dynamic Sunlight: {sunOn ? "ON" : "OFF"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Focus popover */}
          <div className="relative">
            <button
              onClick={() => togglePopover("focus")}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium backdrop-blur-xl shadow-lg transition-all ${
                activePopover === "focus"
                  ? "border-sky-500/60 bg-sky-950/90 text-sky-300"
                  : "border-slate-700/70 bg-slate-900/80 text-slate-300 hover:text-white hover:border-slate-500"
              }`}
            >
              <span>⊹</span>
              <span>Focus</span>
            </button>

            {activePopover === "focus" && (
              <div className="absolute top-full left-0 mt-2 w-44 rounded-xl border border-slate-700/70 bg-slate-900/95 p-2 backdrop-blur-xl shadow-2xl animate-slide-up">
                <button
                  onClick={handleFitScene}
                  className="flex items-center gap-2 w-full rounded-lg px-3 py-2 text-xs text-left text-slate-300 hover:bg-slate-800 transition-colors"
                >
                  🎯 Fit Analysis Area
                </button>
                <button
                  onClick={() => { if (viewerRef.current) viewerRef.current.camera.flyHome(1.5); setActivePopover(null); }}
                  className="flex items-center gap-2 w-full rounded-lg px-3 py-2 text-xs text-left text-slate-300 hover:bg-slate-800 transition-colors"
                >
                  🌍 Global View
                </button>
              </div>
            )}
          </div>

          {/* Time indicator (contextual — only if temporal) */}
          {layerDates.length >= 2 && (
            <div className="flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-900/80 px-3 py-1.5 text-xs backdrop-blur-xl shadow-lg">
              <span className="text-slate-400 font-mono">
                {new Date(layerDates[0]).toLocaleDateString("en-GB", { month: "short" })}
              </span>
              <span className="text-slate-600">───</span>
              <span className="text-slate-300 font-mono font-semibold">
                {new Date(layerDates[layerDates.length - 1]).toLocaleDateString("en-GB", { month: "short", year: "2-digit" })}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Result features count badge (top right, minimal) */}
      {!showIdleOverlay && features.length > 0 && (
        <div className="absolute right-3 top-3 z-20 rounded-xl border border-slate-700/70 bg-slate-900/80 px-3 py-1.5 text-xs backdrop-blur-xl shadow-lg text-slate-300">
          <span className="font-mono text-sky-400">{features.length}</span> features detected
        </div>
      )}
    </div>
  );
}
