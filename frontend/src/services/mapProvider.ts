// Imagery/terrain provider swap point (PRD §11.4).
//
// Default: OpenStreetMap raster tiles + smooth Ellipsoid terrain — fully open,
// no Cesium ion account or token. To go 100% offline / self-hosted, replace
// `createViewer`'s imageryProvider with a locally served XYZ/WMTS endpoint
// (e.g., your own Sentinel-2 composite) — nothing else in the app changes.

const OSM_URL = "https://tile.openstreetmap.org/";
const OSM_ATTRIBUTION =
  "&copy; OpenStreetMap contributors — imagery for development preview; not for operational use";

export function createViewer(container: HTMLElement): any {
  const Cesium = window.Cesium;
  const viewer = new Cesium.Viewer(container, {
    imageryProvider: new Cesium.UrlTemplateImageryProvider({
      url: OSM_URL + "{z}/{x}/{y}.png",
      credit: OSM_ATTRIBUTION,
      maximumLevel: 19,
    }),
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    selectionIndicator: false,
    infoBox: false,
    requestRenderMode: false,
  });
  viewer.scene.globe.enableLighting = false;
  viewer.cesiumWidget.creditContainer.style.display = "none";
  return viewer;
}

export function toCartographicDegrees(cartesian: any): { lon: number; lat: number } {
  const Cesium = window.Cesium;
  const carto = Cesium.Cartographic.fromCartesian(cartesian);
  return { lon: Cesium.Math.toDegrees(carto.longitude), lat: Cesium.Math.toDegrees(carto.latitude) };
}

export function flyToBounds(viewer: any, bounds: number[]): void {
  const Cesium = window.Cesium;
  viewer.camera.flyTo({
    destination: Cesium.Rectangle.fromDegrees(bounds[0], bounds[1], bounds[2], bounds[3]),
    duration: 1.2,
  });
}
