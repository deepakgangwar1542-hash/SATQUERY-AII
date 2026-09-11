// Photorealistic Imagery & Geospatial Atmosphere Provider (§11.4).
//
// Default: High-Resolution TrueColor ESRI World Imagery (sub-meter to 15m global
// satellite photography) with realistic atmospheric Rayleigh scattering, HDR lighting,
// dynamic sun terminator, and starfield. 100% open, zero tokens required.

export type BasemapMode = "satellite" | "dark" | "streets";

export const BASEMAPS: Record<
  BasemapMode,
  { name: string; icon: string; url: string; credit: string; maxLevel: number }
> = {
  satellite: {
    name: "TrueColor Satellite",
    icon: "🛰️",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    credit: "Esri, Maxar, Earthstar Geographics, CNES/Airbus DS, USGS, AeroGRID, IGN",
    maxLevel: 19,
  },
  dark: {
    name: "Tactical Night",
    icon: "🌌",
    url: "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    credit: "© CARTO, © OpenStreetMap",
    maxLevel: 19,
  },
  streets: {
    name: "Street Map",
    icon: "🗺️",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    credit: "© OpenStreetMap contributors",
    maxLevel: 19,
  },
};

export function createViewer(container: HTMLElement, initialBasemap: BasemapMode = "satellite"): any {
  const Cesium = window.Cesium;
  const bm = BASEMAPS[initialBasemap];

  const imageryProvider = new Cesium.UrlTemplateImageryProvider({
    url: bm.url,
    credit: bm.credit,
    maximumLevel: bm.maxLevel,
  });

  const viewer = new Cesium.Viewer(container, {
    imageryProvider,
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

  const scene = viewer.scene;
  const globe = scene.globe;

  // --- Photorealistic Atmosphere & Celestial Lighting ---
  globe.enableLighting = true; // Realistic day/night sunlight terminator
  globe.showGroundAtmosphere = true; // Blue atmospheric rim glow
  globe.atmosphereLightIntensity = 10.0;
  // Earth-accurate Rayleigh scattering (ISS blue orbital horizon)
  globe.atmosphereRayleighCoefficient = new Cesium.Cartesian3(5.5e-6, 13.0e-6, 22.4e-6);
  globe.atmosphereMieCoefficient = new Cesium.Cartesian3(4.0e-6, 4.0e-6, 4.0e-6);
  globe.baseColor = Cesium.Color.fromCssColorString("#020617");

  // High Dynamic Range (HDR) & Atmospheric Scattering
  scene.highDynamicRange = true;
  if (scene.skyAtmosphere) {
    scene.skyAtmosphere.show = true;
    scene.skyAtmosphere.saturationShift = 0.15;
    scene.skyAtmosphere.brightnessShift = 0.05;
  }

  // Realistic Fog & Horizon Depth
  scene.fog.enabled = true;
  scene.fog.density = 0.00012;
  scene.fog.screenSpaceErrorFactor = 2.0;

  // Sun, Moon & Celestial Stars
  scene.sun.show = true;
  scene.moon.show = true;
  if (scene.skyBox) {
    scene.skyBox.show = true;
  }

  // Anti-aliasing & High-DPI Sharpness
  if (scene.postProcessStages?.fxaa) {
    scene.postProcessStages.fxaa.enabled = true;
  }
  viewer.resolutionScale = Math.min(window.devicePixelRatio || 1.0, 2.0);

  // Smooth camera zoom bounds
  if (scene.screenSpaceCameraController) {
    scene.screenSpaceCameraController.minimumZoomDistance = 30.0;
  }

  // Hide bottom unstyled credit container
  if (viewer.cesiumWidget?.creditContainer) {
    viewer.cesiumWidget.creditContainer.style.display = "none";
  }

  return viewer;
}

export function setBasemap(viewer: any, mode: BasemapMode): void {
  const Cesium = window.Cesium;
  const bm = BASEMAPS[mode];
  if (!bm || !viewer) return;

  const layers = viewer.imageryLayers;
  if (layers.length > 0) {
    layers.remove(layers.get(0));
  }

  const provider = new Cesium.UrlTemplateImageryProvider({
    url: bm.url,
    credit: bm.credit,
    maximumLevel: bm.maxLevel,
  });

  layers.addImageryProvider(provider, 0);
}

export function setLightingEnabled(viewer: any, enabled: boolean): void {
  if (!viewer?.scene?.globe) return;
  viewer.scene.globe.enableLighting = enabled;
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
    duration: 1.5,
  });
}
