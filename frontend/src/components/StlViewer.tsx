import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

type Props = {
  url: string;
  height?: number;
};

export default function StlViewer({ url, height = 480 }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errMsg, setErrMsg] = useState<string>("");
  const [triCount, setTriCount] = useState<number>(0);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const width = mount.clientWidth;
    const h = height;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1d24);

    const camera = new THREE.PerspectiveCamera(40, width / h, 0.1, 10000);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, h);
    renderer.setPixelRatio(window.devicePixelRatio);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0x707070));
    const key = new THREE.DirectionalLight(0xffffff, 1.4);
    key.position.set(-200, 250, 300);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffe7c2, 0.45);
    fill.position.set(300, -100, 200);
    scene.add(fill);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    let mesh: THREE.Mesh | null = null;
    let disposed = false;

    const loader = new STLLoader();
    loader.load(
      url,
      (geometry) => {
        if (disposed) return;
        geometry.computeVertexNormals();
        geometry.center();

        const material = new THREE.MeshStandardMaterial({
          color: 0xb38c5f,
          metalness: 0.04,
          roughness: 0.72,
          side: THREE.DoubleSide,
        });
        mesh = new THREE.Mesh(geometry, material);
        // STL ships Z-up; rotate so the relief faces the camera in our default view
        mesh.rotation.x = -Math.PI / 2;
        scene.add(mesh);

        // Frame the model
        const bbox = new THREE.Box3().setFromObject(mesh);
        const size = new THREE.Vector3();
        bbox.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        camera.position.set(0, maxDim * 0.4, maxDim * 1.9);
        camera.lookAt(0, 0, 0);
        controls.target.set(0, 0, 0);
        controls.maxDistance = maxDim * 6;
        controls.minDistance = maxDim * 0.5;
        controls.update();

        const attr = geometry.getAttribute("position");
        if (attr) setTriCount(attr.count / 3);
        setStatus("ready");
      },
      undefined,
      (err) => {
        if (disposed) return;
        const msg = err instanceof Error ? err.message : String(err);
        setErrMsg(msg || "Failed to load STL");
        setStatus("error");
      }
    );

    let frameId = 0;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      if (!mount) return;
      const w = mount.clientWidth;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      disposed = true;
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      if (mesh) {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
      renderer.dispose();
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [url, height]);

  return (
    <div>
      <div
        ref={mountRef}
        style={{
          width: "100%",
          height,
          borderRadius: 8,
          overflow: "hidden",
          background: "#1a1d24",
        }}
      />
      <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
        {status === "loading" && (
          <>
            <span className="spinner" /> Loading STL…
          </>
        )}
        {status === "ready" && (
          <>
            Drag to rotate · scroll to zoom · right-click to pan ·{" "}
            <b>{triCount.toLocaleString()}</b> triangles
          </>
        )}
        {status === "error" && (
          <span className="error">Could not load STL: {errMsg}</span>
        )}
      </div>
    </div>
  );
}
