import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const loader = new STLLoader();
let savedPreviewView = null;

function capturePreviewView(camera, controls) {
  return {
    cameraPosition: camera.position.toArray(),
    target: controls.target.toArray(),
  };
}

function restorePreviewView(camera, controls) {
  if (savedPreviewView === null) {
    return false;
  }

  camera.position.fromArray(savedPreviewView.cameraPosition);
  controls.target.fromArray(savedPreviewView.target);
  controls.update();
  return true;
}

function viewerSize(element) {
  const widthHint = Number(element.dataset.viewerWidth) || 720;
  const heightHint = Number(element.dataset.viewerHeight) || 480;
  const width = Math.max(element.clientWidth || widthHint, 320);
  const height = Math.max(element.clientHeight || heightHint, 240);
  return { width, height };
}

async function renderPreview(element) {
  if (element.dataset.bound === "true") {
    return;
  }

  element.dataset.bound = "true";
  const status = element.querySelector("[data-viewer-status]");

  try {
    const response = await fetch(element.dataset.stlUrl, {
      headers: { Accept: "model/stl" },
    });
    if (!response.ok) {
      throw new Error(`Preview request failed with ${response.status}`);
    }

    const geometry = loader.parse(await response.arrayBuffer());
    geometry.rotateX(-Math.PI / 2);
    geometry.computeVertexNormals();
    geometry.computeBoundingBox();

    if (geometry.boundingBox === null) {
      throw new Error("Preview geometry has no bounds");
    }

    const originalBounds = geometry.boundingBox.clone();
    const centeredX = (originalBounds.min.x + originalBounds.max.x) / 2;
    const centeredZ = (originalBounds.min.z + originalBounds.max.z) / 2;
    geometry.translate(-centeredX, -originalBounds.min.y, -centeredZ);
    geometry.computeBoundingBox();

    if (geometry.boundingBox === null) {
      throw new Error("Preview geometry bounds could not be recomputed");
    }

    const bounds = geometry.boundingBox.clone();
    const size = new THREE.Vector3();
    bounds.getSize(size);
    const maxDimension = Math.max(size.x, size.y, size.z, 10);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.domElement.setAttribute("aria-label", "Interactive 3D STL preview");

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, maxDimension * 20);
    camera.position.set(maxDimension * 1.4, maxDimension * 1.1, maxDimension * 1.4);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    if (!restorePreviewView(camera, controls)) {
      controls.target.set(0, size.y * 0.4, 0);
      controls.update();
    }
    savedPreviewView = capturePreviewView(camera, controls);
    controls.addEventListener("change", () => {
      savedPreviewView = capturePreviewView(camera, controls);
    });

    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.8);
    keyLight.position.set(maxDimension, maxDimension * 2, maxDimension);
    scene.add(keyLight);

    const gridSize = Math.ceil(maxDimension * 3);
    scene.add(new THREE.GridHelper(gridSize, Math.max(Math.round(gridSize / 2), 2)));
    scene.add(new THREE.AxesHelper(Math.max(maxDimension * 0.75, 10)));

    const material = new THREE.MeshStandardMaterial({
      color: 0xb87333,
      roughness: 0.45,
      metalness: 0.05,
    });
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    if (status) {
      status.remove();
    }

    element.appendChild(renderer.domElement);
    element.getPreviewView = () => capturePreviewView(camera, controls);

    const resize = () => {
      const { width, height } = viewerSize(element);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    resize();
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(element);

    let frameHandle = 0;
    const tick = () => {
      controls.update();
      renderer.render(scene, camera);
      frameHandle = window.requestAnimationFrame(tick);
    };
    tick();

    element.cleanupPreview = () => {
      resizeObserver.disconnect();
      window.cancelAnimationFrame(frameHandle);
      element.getPreviewView = undefined;
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  } catch (error) {
    if (status) {
      status.textContent = error instanceof Error ? error.message : "Preview failed";
    }
  }
}

function initializePreviews(root = document) {
  root.querySelectorAll(".js-model-preview").forEach((element) => {
    renderPreview(element);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initializePreviews(document);
});

document.body.addEventListener("htmx:beforeSwap", (event) => {
  const previews = event.detail.target?.querySelectorAll?.(".js-model-preview") ?? [];
  previews.forEach((preview) => {
    if (typeof preview.cleanupPreview === "function") {
      preview.cleanupPreview();
    }
  });
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  initializePreviews(event.detail.target);
});
