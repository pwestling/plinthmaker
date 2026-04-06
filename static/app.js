import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const loader = new STLLoader();
let savedPreviewView = null;
let savedPreviewLayoutKey = null;
const MIN_SCENE_DIMENSION = 10;
const SCALE_REFERENCE_GAP_RATIO = 0.15;

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

async function loadStlGeometry(url) {
  const response = await fetch(url, {
    headers: { Accept: "model/stl" },
  });
  if (!response.ok) {
    throw new Error(`Preview request failed with ${response.status}`);
  }

  return loader.parse(await response.arrayBuffer());
}

function normalizeGeometry(geometry, rotationX = -Math.PI / 2) {
  geometry.rotateX(rotationX);
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
  return { geometry, bounds, size };
}

function translatedBounds(bounds, offset) {
  return bounds.clone().translate(offset);
}

async function renderPreview(element) {
  if (element.dataset.bound === "true") {
    return;
  }

  element.dataset.bound = "true";
  const status = element.querySelector("[data-viewer-status]");

  try {
    const showScaleReference = element.dataset.showScaleReference === "true";
    const layoutKey = showScaleReference ? "with-scale-reference" : "plinth-only";
    const shouldRestoreSavedView = savedPreviewLayoutKey === layoutKey;
    if (!shouldRestoreSavedView) {
      savedPreviewView = null;
      savedPreviewLayoutKey = layoutKey;
    }
    const [mainGeometry, scaleGeometry] = await Promise.all([
      loadStlGeometry(element.dataset.stlUrl),
      showScaleReference
        ? loadStlGeometry(element.dataset.scaleReferenceUrl)
        : Promise.resolve(null),
    ]);
    const mainModel = normalizeGeometry(mainGeometry);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.domElement.setAttribute("aria-label", "Interactive 3D STL preview");

    const scene = new THREE.Scene();
    const sceneBounds = mainModel.bounds.clone();
    const disposables = [mainModel.geometry];

    const plinthMaterial = new THREE.MeshStandardMaterial({
      color: 0xb87333,
      roughness: 0.45,
      metalness: 0.05,
    });
    disposables.push(plinthMaterial);
    const plinthMesh = new THREE.Mesh(mainModel.geometry, plinthMaterial);
    scene.add(plinthMesh);

    if (scaleGeometry !== null) {
      const scaleModel = normalizeGeometry(scaleGeometry, 0);
      const gap = Math.max(
        mainModel.size.x,
        scaleModel.size.x,
        MIN_SCENE_DIMENSION,
      ) * SCALE_REFERENCE_GAP_RATIO;
      const scaleOffset = new THREE.Vector3(
        mainModel.bounds.max.x + gap + scaleModel.size.x / 2,
        0,
        0,
      );
      const scaleMaterial = new THREE.MeshStandardMaterial({
        color: 0x8c8c8c,
        roughness: 0.6,
        metalness: 0.05,
        transparent: true,
        opacity: 0.9,
      });
      disposables.push(scaleModel.geometry, scaleMaterial);
      const scaleMesh = new THREE.Mesh(scaleModel.geometry, scaleMaterial);
      scaleMesh.position.copy(scaleOffset);
      scene.add(scaleMesh);

      const scaleBounds = translatedBounds(scaleModel.bounds, scaleOffset);
      sceneBounds.expandByPoint(scaleBounds.min);
      sceneBounds.expandByPoint(scaleBounds.max);
    }

    const sceneSize = new THREE.Vector3();
    sceneBounds.getSize(sceneSize);
    const sceneCenter = new THREE.Vector3();
    sceneBounds.getCenter(sceneCenter);
    const maxDimension = Math.max(
      sceneSize.x,
      sceneSize.y,
      sceneSize.z,
      MIN_SCENE_DIMENSION,
    );

    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, maxDimension * 20);
    camera.position.copy(
      sceneCenter.clone().add(
        new THREE.Vector3(maxDimension * 1.4, maxDimension * 1.1, maxDimension * 1.4),
      ),
    );

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    if (shouldRestoreSavedView && restorePreviewView(camera, controls)) {
      // Keep the existing view when the preview content changes but the scene layout does not.
    } else {
      controls.target.set(
        sceneCenter.x,
        sceneBounds.min.y + sceneSize.y * 0.35,
        sceneCenter.z,
      );
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

    const gridSize = Math.ceil(
      Math.max(sceneSize.x, sceneSize.z, MIN_SCENE_DIMENSION) * 3,
    );
    scene.add(new THREE.GridHelper(gridSize, Math.max(Math.round(gridSize / 2), 2)));
    scene.add(new THREE.AxesHelper(Math.max(maxDimension * 0.75, 10)));

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
      disposables.forEach((resource) => {
        resource.dispose();
      });
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
