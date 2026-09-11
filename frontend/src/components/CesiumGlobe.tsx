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
  activeLayerKey: string | null;
  layerDates: string[];
}

const CHANGE_COLORS: Record<string, string> = {
  vegetation_loss: "#f97316", // Orange
  vegetation_gain: "#22c55e", // Emerald
  water_loss: "#eab308",      // Amber
  water_gain: "#3b82f6",      // Blue
  detection: "#e879f9",       // Fuchsia
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
  features,
  footprintBounds,
  drawMode,
  onAoiDrawn,
  activeLayerKey,
  layerDates,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const handlerRef = useRef<any>(null);
  const drawPtsRef = useRef<{ lon: number; lat: number }[]>([]);
  const [currentBasemap, setCurrentBasemap] = useState<BasemapMode>("satellite");
  const [sunLighting, setSunLighting] = useState(true);
  const [filterLayer, setFilterLayer] = useState<"all" | "change" | "detections">("all");
  const [selectedEntityInfo, setSelectedEntityInfo] = useState<{
    title: string;
    category: string;
    areaKm2?: number;
    confidence?: number;
  } | null>(null);

  // Initialize Cesium viewer
  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;
    const viewer = createViewer(containerRef.current);
    viewerRef.current = viewer;

    // Entity click listener
    const handler = new (window.Cesium.ScreenSpaceEventHandler)(viewer.scene.canvas);
    handler.setInputAction((movement: any) => {
      const pickedObject = viewer.scene.pick(movement.position);
      if (window.Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id._satqueryProps) {
        setSelectedEntityInfo(pickedObject.id._satqueryProps);
      } else {
        setSelectedEntityInfo(null);
      }
    }, window.Cesium.ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // Fly to satellite footprint bounds when loaded
  useEffect(() => {
    if (viewerRef.current && footprintBounds && footprintBounds.length === 4) {
      flyToBounds(viewerRef.current, footprintBounds);
    }
  }, [footprintBounds]);

  // Render result features as glowing entities on the 3D globe
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.entities.removeAll();

    const filtered = features.filter((f) => {
      if (filterLayer === "all") return true;
      const isDet = f.properties?.kind === "detection" || f.properties?.type === "detection";
      if (filterLayer === "detections") return isDet;
      return !isDet;
    });

    const Cesium = window.Cesium;

    for (const f of filtered.slice(0, 500)) {
      const colorHex = colorFor(f);
      const color = Cesium.Color.fromCssColorString(colorHex).withAlpha(0.5);
      const outline = Cesium.Color.fromCssColorString(colorHex);
      const geom = f.geometry;
      if (!geom) continue;

      const props = f.properties || {};
      const entityProps = {
        title: props.label || props.change_class || props.name || "Remote Sensing Feature",
        category: props.kind || props.change_class || "Detection",
        areaKm2: props.area_km2,
        confidence: props.confidence,
      };

      if (geom.type === "Polygon") {
        const rings = geom.coordinates as number[][][];
        const hierarchy = rings[0].map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat));
        const ent = viewer.entities.add({
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(hierarchy),
            material: color,
            outline: true,
            outlineColor: outline,
            outlineWidth: 2,
          },
          polyline: {
            positions: [...hierarchy, hierarchy[0]],
            width: 2.5,
            material: outline,
          },
        });
        ent._satqueryProps = entityProps;
      } else if (geom.type === "MultiPolygon") {
        for (const poly of geom.coordinates as number[][][][]) {
          const hierarchy = poly[0].map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat));
          const ent = viewer.entities.add({
            polygon: {
              hierarchy: new Cesium.PolygonHierarchy(hierarchy),
              material: color,
              outline: true,
              outlineColor: outline,
            },
          });
          ent._satqueryProps = entityProps;
        }
      } else if (geom.type === "Point") {
        const [lon, lat] = geom.coordinates as number[];
        const ent = viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(lon, lat),
          point: {
            pixelSize: 10,
            color: outline,
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2,
          },
          label: {
            text: props.label || "Object Target",
            font: "11px Inter, sans-serif",
            fillColor: Cesium.Color.WHITE,
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(0.7),
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            pixelOffset: new Cesium.Cartesian2(0, -10),
          },
        });
        ent._satqueryProps = entityProps;
      }
    }
  }, [features, filterLayer]);

  // AOI drawing: click vertices, double-click closes the polygon
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const Cesium = window.Cesium;
    handlerRef.current?.destroy();
    drawPtsRef.current = [];

    if (!drawMode) return;
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handlerRef.current = handler;

    const tempEntity = viewer.entities.add({
      polyline: {
        positions: [],
        width: 3,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.25,
          color: Cesium.Color.YELLOW,
        }),
      },
    });

    const updateLine = () => {
      const pts = drawPtsRef.current;
      const positions = pts.map((p) => Cesium.Cartesian3.fromDegrees(p.lon, p.lat));
      if (positions.length > 0 && drawMode) {
        tempEntity.polyline.positions =
          positions.length > 1 ? positions : [...positions, positions[0]];
      }
    };

    handler.setInputAction((click: any) => {
      const cartesian = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);
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
    }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

    return () => {
      handler.destroy();
      handlerRef.current = null;
    };
  }, [drawMode, onAoiDrawn]);

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
      {/* Cesium canvas target */}
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />

      {/* FLOATING GLASS HUD TOOLBAR (Top Left) */}
      <div className="absolute left-3 top-3 z-20 flex flex-wrap items-center gap-1.5 pointer-events-auto">
        {/* Basemap Switcher Pill */}
        <div className="flex items-center gap-1 rounded-xl border border-slate-700/70 bg-slate-900/85 p-1 backdrop-blur-xl shadow-2xl">
          {(Object.keys(BASEMAPS) as BasemapMode[]).map((mode) => {
            const bm = BASEMAPS[mode];
            const isActive = currentBasemap === mode;
            return (
              <button
                key={mode}
                onClick={() => handleBasemapChange(mode)}
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all cursor-pointer ${
                  isActive
                    ? "bg-sky-600 text-white shadow-sm font-semibold"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <span>{bm.icon}</span>
                <span className="hidden sm:inline">{bm.name}</span>
              </button>
            );
          })}

          <div className="h-3 w-px bg-slate-700 mx-0.5" />

          {/* Dynamic Sun Lighting Toggle */}
          <button
            onClick={handleToggleLighting}
            title="Toggle realistic dynamic sunlight and day/night terminator"
            className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition-all cursor-pointer ${
              sunLighting
                ? "bg-amber-600/30 text-amber-300 border border-amber-500/40 font-semibold"
                : "text-slate-400 hover:bg-slate-800"
            }`}
          >
            <span>☀️</span>
            <span className="hidden sm:inline">Sun: {sunLighting ? "ON" : "OFF"}</span>
          </button>
        </div>

        {/* Re-center & Scene Telemetry Pill */}
        {footprintBounds && (
          <button
            onClick={handleRecenter}
            title="Fly camera to active satellite scene extent"
            className="flex items-center gap-1.5 rounded-xl border border-sky-500/40 bg-slate-900/85 hover:bg-sky-600 px-3 py-1.5 text-[11px] font-bold text-slate-100 hover:text-white backdrop-blur-xl shadow-lg transition-all cursor-pointer"
          >
            <span>🎯</span>
            <span>Focus Scene</span>
          </button>
        )}

        {/* Layer Visibility Pills (when features exist) */}
        {features.length > 0 && (
          <div className="flex items-center gap-1 rounded-xl border border-slate-700/70 bg-slate-900/85 p-1 backdrop-blur-xl shadow-2xl text-[11px]">
            <button
              onClick={() => setFilterLayer("all")}
              className={`rounded-lg px-2 py-1 font-medium transition-all cursor-pointer ${
                filterLayer === "all" ? "bg-indigo-600 text-white font-semibold" : "text-slate-400 hover:text-white"
              }`}
            >
              All ({features.length})
            </button>
            <button
              onClick={() => setFilterLayer("change")}
              className={`rounded-lg px-2 py-1 font-medium transition-all cursor-pointer ${
                filterLayer === "change" ? "bg-orange-600 text-white font-semibold" : "text-slate-400 hover:text-white"
              }`}
            >
              Change Polygons
            </button>
            <button
              onClick={() => setFilterLayer("detections")}
              className={`rounded-lg px-2 py-1 font-medium transition-all cursor-pointer ${
                filterLayer === "detections" ? "bg-fuchsia-600 text-white font-semibold" : "text-slate-400 hover:text-white"
              }`}
            >
              Detections
            </button>
          </div>
        )}
      </div>

      {/* DRAW MODE NOTICE */}
      {drawMode && (
        <div className="absolute top-14 left-3 z-20 animate-pulse rounded-xl border border-amber-500/60 bg-amber-950/85 px-3 py-2 text-xs text-amber-200 backdrop-blur-xl shadow-2xl pointer-events-auto">
          <div className="font-bold flex items-center gap-1.5">
            <span>✏️</span>
            <span>AOI Drawing Mode Active</span>
          </div>
          <p className="text-[10px] text-amber-300/90 mt-0.5">
            Click points on the globe to place vertices. Double-click to close polygon.
          </p>
        </div>
      )}

      {/* SELECTED ENTITY POPUP (Bottom Left on Globe) */}
      {selectedEntityInfo && (
        <div className="absolute bottom-6 left-4 z-20 rounded-xl border border-sky-500/50 bg-slate-900/90 p-3 backdrop-blur-xl shadow-2xl text-xs space-y-1 max-w-xs pointer-events-auto animate-fadeIn">
          <div className="flex items-center justify-between border-b border-slate-800 pb-1">
            <span className="font-bold text-sky-300 font-display">{selectedEntityInfo.title}</span>
            <button
              onClick={() => setSelectedEntityInfo(null)}
              className="text-slate-400 hover:text-white text-xs ml-2 cursor-pointer"
            >
              ✕
            </button>
          </div>
          <div className="text-[11px] text-slate-300">
            Category: <span className="font-mono text-slate-200">{selectedEntityInfo.category}</span>
          </div>
          {selectedEntityInfo.areaKm2 !== undefined && (
            <div className="text-[11px] text-slate-300">
              Area: <span className="font-mono text-emerald-400">{selectedEntityInfo.areaKm2.toFixed(4)} km²</span>
            </div>
          )}
          {selectedEntityInfo.confidence !== undefined && (
            <div className="text-[11px] text-slate-300">
              Model Confidence: <span className="font-mono text-sky-400">{(selectedEntityInfo.confidence * 100).toFixed(0)}%</span>
            </div>
          )}
        </div>
      )}

      {/* VISUAL LEGEND (Top Right) */}
      <div className="absolute right-3 top-3 z-20 pointer-events-auto">
        <div className="rounded-xl border border-slate-700/70 bg-slate-900/85 p-2.5 backdrop-blur-xl shadow-2xl text-xs space-y-1.5 max-w-[190px]">
          <div className="flex items-center justify-between border-b border-slate-800 pb-1 text-[10px] uppercase font-bold tracking-wider text-slate-400">
            <span>Visual Evidence</span>
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
              <span className="text-slate-300">DINO Target</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
