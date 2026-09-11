/// <reference types="vite/client" />

declare global {
  interface Window {
    Cesium: any; // loaded from the self-hosted static build (§11.4)
    CESIUM_BASE_URL?: string;
  }
}

export {};
