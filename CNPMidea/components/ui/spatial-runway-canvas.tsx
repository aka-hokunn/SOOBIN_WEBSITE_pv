"use client";

import React, { Suspense, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  Float,
  Sparkles,
  Environment,
  MeshDistortMaterial,
  OrbitControls,
} from "@react-three/drei";
import Spline from "@splinetool/react-spline";
import { useRive } from "@rive-app/react-canvas";
import NumberFlow from "@number-flow/react";
import { Command } from "cmdk";
import { Toaster, toast } from "sonner";
import * as THREE from "three";

function OceanPearlSculpture({ accentColor = "#22d3ee" }: { accentColor?: string }) {
  const meshRef = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!meshRef.current) return;
    meshRef.current.rotation.y = state.clock.getElapsedTime() * 0.45;
    meshRef.current.rotation.x = Math.sin(state.clock.getElapsedTime() * 0.6) * 0.2;
  });

  return (
    <Float speed={2.2} rotationIntensity={0.8} floatIntensity={1.4}>
      <mesh ref={meshRef} castShadow receiveShadow>
        <torusKnotGeometry args={[1.1, 0.34, 180, 32]} />
        <MeshDistortMaterial
          color={accentColor}
          roughness={0.15}
          metalness={0.75}
          distort={0.28}
          speed={2.2}
        />
      </mesh>
    </Float>
  );
}

/**
 * SpatialRunwayCanvas (Rule #3 of antigravityrules.md)
 * Combines `@react-three/fiber`, `@react-three/drei`, `@splinetool/react-spline`,
 * `@rive-app/react-canvas`, `@number-flow/react`, `cmdk`, and `sonner`.
 */
export function SpatialRunwayCanvas({
  splineSceneUrl,
  riveSrc,
  activeMetric = 1285000,
}: {
  splineSceneUrl?: string;
  riveSrc?: string;
  activeMetric?: number;
}) {
  const { RiveComponent } = useRive({
    src: riveSrc || "",
    autoplay: true,
  });

  return (
    <div className="relative w-full h-96 rounded-3xl overflow-hidden bg-slate-950 border border-white/10">
      <Toaster richColors position="bottom-right" />
      {splineSceneUrl ? (
        <Suspense fallback={<div className="p-8 text-xs text-cyan-300">Đang tải Spline 3D Scene...</div>}>
          <Spline scene={splineSceneUrl} />
        </Suspense>
      ) : (
        <Canvas camera={{ position: [0, 0, 4.2], fov: 42 }} dpr={[1, 2]}>
          <ambientLight intensity={0.7} />
          <directionalLight position={[4, 6, 4]} intensity={1.8} />
          <Sparkles count={90} scale={6} size={2.2} speed={0.4} color="#67e8f9" />
          <OceanPearlSculpture />
          <Environment preset="city" />
          <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={1.2} />
        </Canvas>
      )}

      {riveSrc && (
        <div className="absolute top-4 right-4 w-16 h-16 pointer-events-auto">
          <RiveComponent />
        </div>
      )}

      <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between px-4 py-2.5 rounded-2xl bg-slate-900/80 backdrop-blur-md border border-white/10 text-xs text-white">
        <div>
          <span className="text-[10px] uppercase tracking-widest text-cyan-300 block font-bold">
            Realtime Luxury Value (NumberFlow)
          </span>
          <NumberFlow
            value={activeMetric}
            format={{ style: "currency", currency: "VND" }}
            className="text-lg font-extrabold text-white"
          />
        </div>
        <button
          onClick={() => toast.success("Đã kích hoạt chế độ trình diễn 3D Spatial Runway!")}
          className="px-3.5 py-1.5 rounded-xl bg-cyan-500 text-slate-950 font-extrabold"
        >
          Trải Nghiệm Ngay
        </button>
      </div>
    </div>
  );
}

