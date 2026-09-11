import { useEffect, useRef, useState } from "react";
import { createViewer, flyToBounds, toCartographicDegrees } from "../services/mapProvider";

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

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {drawMode && (
        <div className="absolute left-2 top-2 rounded bg-slate-900/90 px-2 py-1 text-xs text-sky-300">
          AOI draw mode: click vertices, double-click to close
        </div>
      )}
      {!drawMode && drawing === false && layerDates.length > 1 && activeLayerKey && (
        <div className="absolute left-2 top-2 rounded bg-slate-900/80 px-2 py-1 text-xs text-slate-300">
          replaying: {activeLayerKey}
        </div>
      )}
    </div>
  );
}
