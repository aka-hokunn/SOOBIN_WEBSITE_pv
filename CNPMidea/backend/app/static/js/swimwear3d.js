// =============================================================================
// SOOBIN SWIMWEAR — REAL-TIME 3D ANATOMICAL MANNEQUIN & GARMENT WEBGL ENGINE
// =============================================================================
// Generates high-density parametric 3D anatomical mannequin meshes and
// contoured 3D swimwear garments (Bikini, Monokini, Jammer, Rashguard, Goggles)
// with procedural Lycra micro-weave bump maps, raised 3D seam piping,
// animated water surface pedestal, and interactive 360° orbit controls.
// =============================================================================

(function () {
  "use strict";

  const activeViewers = new Map();

  // Create a procedural Lycra hexagonal micro-weave bump & pattern canvas texture
  function createFabricTextures(baseHex, accentHex, productImgUrl, onReady) {
    const size = 512;
    const diffCanvas = document.createElement("canvas");
    diffCanvas.width = size;
    diffCanvas.height = size;
    const dCtx = diffCanvas.getContext("2d");

    const bumpCanvas = document.createElement("canvas");
    bumpCanvas.width = size;
    bumpCanvas.height = size;
    const bCtx = bumpCanvas.getContext("2d");

    function drawWeavePattern(imgElement) {
      // 1. Base color or sampled image gradient
      const grad = dCtx.createLinearGradient(0, 0, size, size);
      grad.addColorStop(0, baseHex || "#0284c7");
      grad.addColorStop(0.65, baseHex || "#0284c7");
      grad.addColorStop(1, accentHex || "#06b6d4");
      dCtx.fillStyle = grad;
      dCtx.fillRect(0, 0, size, size);

      // Blend subtle product texture pattern if image loaded
      if (imgElement) {
        dCtx.save();
        dCtx.globalAlpha = 0.28;
        dCtx.globalCompositeOperation = "overlay";
        dCtx.drawImage(imgElement, 0, 0, size, size);
        dCtx.restore();
      }

      // 2. Draw micro-Lycra knit weave on both diffuse and bump map
      bCtx.fillStyle = "#808080";
      bCtx.fillRect(0, 0, size, size);

      dCtx.strokeStyle = "rgba(255,255,255,0.07)";
      dCtx.lineWidth = 1;
      bCtx.strokeStyle = "#ffffff";
      bCtx.lineWidth = 1.4;

      const step = 8;
      for (let y = 0; y < size; y += step) {
        for (let x = 0; x < size; x += step) {
          const offset = (y / step) % 2 === 0 ? 0 : step / 2;
          bCtx.beginPath();
          bCtx.arc(x + offset, y, 2.2, 0, Math.PI * 2);
          bCtx.stroke();

          dCtx.beginPath();
          dCtx.arc(x + offset, y, 2.0, 0, Math.PI);
          dCtx.stroke();
        }
      }

      // Hydrodynamic speed lines
      dCtx.strokeStyle = "rgba(255,255,255,0.14)";
      dCtx.lineWidth = 3;
      for (let i = 1; i <= 3; i++) {
        dCtx.beginPath();
        dCtx.moveTo(size * (0.18 * i), 0);
        dCtx.bezierCurveTo(
          size * (0.18 * i + 0.06),
          size * 0.35,
          size * (0.18 * i - 0.06),
          size * 0.65,
          size * (0.18 * i),
          size
        );
        dCtx.stroke();
      }

      if (window.THREE) {
        const diffTex = new THREE.CanvasTexture(diffCanvas);
        diffTex.wrapS = THREE.RepeatWrapping;
        diffTex.wrapT = THREE.RepeatWrapping;
        diffTex.repeat.set(2, 2);

        const bumpTex = new THREE.CanvasTexture(bumpCanvas);
        bumpTex.wrapS = THREE.RepeatWrapping;
        bumpTex.wrapT = THREE.RepeatWrapping;
        bumpTex.repeat.set(6, 6);

        onReady({ diffTex, bumpTex });
      }
    }

    drawWeavePattern(null);

    if (productImgUrl) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => drawWeavePattern(img);
      img.src = productImgUrl;
    }
  }

  // Evaluate 3D anatomical torso cross-section at height y in [-0.62, +1.15] and angle theta in [0, 2PI]
  // theta = 0 is FRONT (+Z), theta = PI/2 is RIGHT (+X), theta = PI is BACK (-Z)
  function evalTorsoPoint(y, theta, isMale, shellOffset) {
    const sinT = Math.sin(theta);
    const cosT = Math.cos(theta);

    // Normalize t from hip (-0.62) to neck (1.15)
    let rx = 0.38;
    let rz = 0.25;

    if (isMale) {
      // Athletic male V-taper torso
      if (y > 0.85) {
        // Neck & upper traps taper
        const k = Math.min(1, (y - 0.85) / 0.32);
        rx = 0.49 * (1 - k) + 0.17 * k;
        rz = 0.27 * (1 - k) + 0.16 * k;
      } else if (y >= 0.15) {
        // Chest & lats
        const k = (y - 0.15) / 0.70;
        rx = 0.38 + 0.11 * Math.sin(k * Math.PI * 0.75);
        rz = 0.24 + 0.05 * Math.sin(k * Math.PI * 0.8);
      } else {
        // Waist to pelvis
        const k = (y - -0.62) / 0.77;
        rx = 0.40 - 0.02 * Math.sin(k * Math.PI);
        rz = 0.25 - 0.015 * Math.sin(k * Math.PI);
      }
    } else {
      // Sculpted female hourglass torso
      if (y > 0.85) {
        const k = Math.min(1, (y - 0.85) / 0.30);
        rx = 0.43 * (1 - k) + 0.145 * k;
        rz = 0.23 * (1 - k) + 0.14 * k;
      } else if (y >= 0.18) {
        // Ribcage & upper torso
        const k = (y - 0.18) / 0.67;
        rx = 0.31 + 0.12 * Math.pow(k, 0.85);
        rz = 0.20 + 0.045 * Math.sin(k * Math.PI * 0.85);
      } else {
        // Waist (y ~ 0.18) flaring out to curvy hips (y ~ -0.35)
        const hipCurve = Math.exp(-Math.pow((y - -0.32) / 0.32, 2));
        rx = 0.31 + 0.145 * hipCurve;
        rz = 0.20 + 0.065 * hipCurve;
      }
    }

    let x = rx * sinT;
    let z = rz * cosT;

    // Anatomical 3D Chest / Bust Sculpting (Front: cosT > 0)
    if (cosT > 0 && y > 0.28 && y < 0.86) {
      const bustY = isMale ? 0.62 : 0.56;
      const bustSpread = isMale ? 0.22 : 0.19;
      const bustHeightFactor = Math.exp(-Math.pow((y - bustY) / bustSpread, 2));
      const leftLobe = Math.exp(-Math.pow((theta - 0.46) / 0.38, 2));
      const rightLobe = Math.exp(-Math.pow((theta - (Math.PI * 2 - 0.46)) / 0.38, 2));
      const bustAmp = isMale ? 0.055 : 0.115;
      z += bustAmp * bustHeightFactor * (leftLobe + rightLobe);
      // Sternum cleavage valley
      const centerValley = Math.exp(-Math.pow(sinT / 0.16, 2)) * Math.max(0, cosT);
      z -= (isMale ? 0.015 : 0.032) * bustHeightFactor * centerValley;
    }

    // Anatomical Spine Groove & Lumbar Curve (Back: cosT < 0)
    if (cosT < 0) {
      const spineGroove = Math.exp(-Math.pow(sinT / 0.18, 2)) * Math.abs(cosT);
      if (y > -0.15 && y < 0.85) {
        z += 0.025 * spineGroove; // Indentation along spine
      }
      // Lumbar arch (lordosis) around y = 0.12
      const lumbar = Math.exp(-Math.pow((y - 0.15) / 0.28, 2));
      z += 0.035 * lumbar * Math.abs(cosT);

      // Sculpted 3D Glutes (y around -0.38, back)
      const gluteY = Math.exp(-Math.pow((y - -0.38) / 0.22, 2));
      const gluteL = Math.exp(-Math.pow((theta - (Math.PI - 0.42)) / 0.36, 2));
      const gluteR = Math.exp(-Math.pow((theta - (Math.PI + 0.42)) / 0.36, 2));
      const gluteAmp = isMale ? 0.075 : 0.105;
      z -= gluteAmp * gluteY * (gluteL + gluteR);
    }

    // Apply shell offset outward for garment layer
    if (shellOffset) {
      const len = Math.sqrt(x * x + z * z) || 1;
      x += (x / len) * shellOffset;
      z += (z / len) * shellOffset;
    }

    return new THREE.Vector3(x, y, z);
  }

  // Determine whether a point (y, theta) on the torso belongs to the 3D garment pattern
  function isPointInTorsoGarment(y, theta, geomType) {
    const cosT = Math.cos(theta); // +1 front, -1 back
    const absSin = Math.abs(Math.sin(theta)); // +1 sides

    // High-leg arch cut at the sides (theta = PI/2 or 3PI/2)
    const legCutY = -0.56 + 0.26 * Math.pow(absSin, 1.6);

    if (geomType === "bikini_3d") {
      // 1. Bikini Top Band & Sculpted Cups
      const inCupFront = cosT > -0.15 && y >= 0.40 && y <= 0.76 - 0.14 * Math.exp(-Math.pow(absSin / 0.22, 2));
      const inBackBand = cosT <= -0.15 && y >= 0.44 && y <= 0.56;
      // Shoulder straps
      const isStrapFront = cosT > 0 && y > 0.70 && y <= 1.05 && Math.abs( absSin - 0.58 ) < 0.11;
      const isStrapBack = cosT <= 0 && y > 0.54 && y <= 1.05 && Math.abs( absSin - 0.54 ) < 0.11;

      // 2. Bikini Bottom V-Waist Brief
      const waistDip = -0.14 - 0.07 * cosT; // dips in front V, slightly higher on hips
      const inBottom = y >= legCutY && y <= waistDip;

      return inCupFront || inBackBand || isStrapFront || isStrapBack || inBottom;
    }

    if (geomType === "jammer_3d") {
      // Men's Jammer starts at waist y = -0.02 down to legs
      return y <= -0.02 && y >= -0.60;
    }

    if (geomType === "rashguard_3d") {
      // High-neck zip-front surf suit covers full torso down to leg arch
      return y >= legCutY && y <= 1.04;
    }

    // Default: onepiece_3d (Sculpted Monokini with scoop neck & keyhole back cutout)
    if (y < legCutY || y > 1.04) return false;
    // Front scoop neckline cutout
    if (cosT > 0.25 && y > 0.74 + 0.28 * Math.pow(absSin, 1.8) && absSin < 0.52) {
      return false;
    }
    // Open keyhole back cutout
    if (cosT < -0.25) {
      const inBackHole = Math.pow((y - 0.36) / 0.26, 2) + Math.pow(absSin / 0.58, 2) < 1.0;
      if (inBackHole) return false;
      // Upper back scoop
      if (y > 0.68 && absSin < 0.48) return false;
    }
    // Armhole cutouts on the sides
    if (absSin > 0.72 && y > 0.56 && y < 1.02) {
      return false;
    }
    return true;
  }

  // Build Parametric 3D Torso BufferGeometry ( either full Mannequin or clipped Garment Shell )
  function buildParametricTorsoGeometry(isMale, shellOffset, geomType, isGarment) {
    const segY = 72;
    const segT = 64;
    const yMin = -0.60;
    const yMax = 1.08;

    const positions = [];
    const uvs = [];
    const indices = [];
    const validGrid = [];

    for (let iy = 0; iy <= segY; iy++) {
      const v = iy / segY;
      const y = yMin + v * (yMax - yMin);
      const rowValid = [];
      for (let it = 0; it <= segT; it++) {
        const u = it / segT;
        const theta = u * Math.PI * 2;
        const pt = evalTorsoPoint(y, theta, isMale, shellOffset);
        positions.push(pt.x, pt.y, pt.z);
        uvs.push(u, v);
        rowValid.push(isGarment ? isPointInTorsoGarment(y, theta, geomType) : true);
      }
      validGrid.push(rowValid);
    }

    for (let iy = 0; iy < segY; iy++) {
      for (let it = 0; it < segT; it++) {
        const a = iy * (segT + 1) + it;
        const b = a + 1;
        const c = (iy + 1) * (segT + 1) + it;
        const d = c + 1;

        if (!isGarment || (validGrid[iy][it] && validGrid[iy][it + 1] && validGrid[iy + 1][it] && validGrid[iy + 1][it + 1])) {
          indices.push(a, b, d);
          indices.push(a, d, c);
        }
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    geo.setIndex(indices);
    geo.computeVertexNormals();
    return geo;
  }

  // Build Sculpted 3D Limb (Leg or Arm) Geometry
  function buildLimbGeometry(yStart, yEnd, xCenterTop, xCenterBot, radTop, radBot, zFlatten, shellOffset) {
    const segY = 32;
    const segT = 32;
    const positions = [];
    const uvs = [];
    const indices = [];

    for (let iy = 0; iy <= segY; iy++) {
      const v = iy / segY;
      const y = yStart + v * (yEnd - yStart);
      const cx = xCenterTop + v * (xCenterBot - xCenterTop);
      // Muscle contour bulge in the middle of thigh/arm
      const muscleBulge = 1.0 + 0.08 * Math.sin(v * Math.PI);
      const r = (radTop + v * (radBot - radTop)) * muscleBulge + (shellOffset || 0);

      for (let it = 0; it <= segT; it++) {
        const u = it / segT;
        const theta = u * Math.PI * 2;
        const x = cx + r * Math.sin(theta);
        const z = r * zFlatten * Math.cos(theta) - 0.02;
        positions.push(x, y, z);
        uvs.push(u, v);
      }
    }

    for (let iy = 0; iy < segY; iy++) {
      for (let it = 0; it < segT; it++) {
        const a = iy * (segT + 1) + it;
        const b = a + 1;
        const c = (iy + 1) * (segT + 1) + it;
        const d = c + 1;
        indices.push(a, b, d);
        indices.push(a, d, c);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    geo.setIndex(indices);
    geo.computeVertexNormals();
    return geo;
  }

  // Build Complete 3D Scene inside any target <canvas>
  function mountSwimwear3DViewer(canvasId, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.THREE) return null;

    // Dispose any existing viewer on this canvas
    if (activeViewers.has(canvasId)) {
      const old = activeViewers.get(canvasId);
      old.destroy();
    }

    const parent = canvas.parentElement;
    const width = parent ? parent.clientWidth || 640 : 640;
    const height = parent ? parent.clientHeight || 460 : 460;

    const geomType = options.geometryType || "onepiece_3d";
    const isMale = geomType === "jammer_3d" || (options.targetAudience || "").toLowerCase() === "nam";
    const primaryColor = options.colorHex || "#0284c7";
    const productImgUrl = options.imageUrl || null;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
    camera.position.set(0, 0.18, 4.35);

    const renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance"
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;

    // Studio 3-Point + Rim Lighting Rig
    const ambientLight = new THREE.AmbientLight(0xe0f2fe, 0.78);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.25);
    keyLight.position.set(3.2, 4.5, 4.0);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x38bdf8, 0.72);
    fillLight.position.set(-3.5, 2.0, 2.5);
    scene.add(fillLight);

    const rimLight = new THREE.PointLight(0x22d3ee, 1.15, 12);
    rimLight.position.set(0, 2.6, -3.2);
    scene.add(rimLight);

    const rootGroup = new THREE.Group();
    scene.add(rootGroup);

    // Materials
    const mannequinMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color("#dbeafe"),
      roughness: 0.36,
      metalness: 0.22
    });

    const garmentMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(primaryColor),
      roughness: 0.28,
      metalness: 0.14,
      side: THREE.DoubleSide
    });

    const seamAccentMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color("#38bdf8"),
      roughness: 0.2,
      metalness: 0.55,
      emissive: new THREE.Color("#0284c7"),
      emissiveIntensity: 0.22
    });

    const wireframeMat = new THREE.MeshBasicMaterial({
      color: 0x67e8f9,
      wireframe: true,
      transparent: true,
      opacity: 0.0
    });

    // Apply procedural Lycra weave + product image texture
    createFabricTextures(primaryColor, "#22d3ee", productImgUrl, ({ diffTex, bumpTex }) => {
      garmentMat.map = diffTex;
      garmentMat.bumpMap = bumpTex;
      garmentMat.bumpScale = 0.012;
      garmentMat.needsUpdate = true;
    });

    const garmentMeshes = [];
    const wireMeshes = [];

    if (geomType === "goggles_3d") {
      // =======================================================================
      // HIGH-DETAIL 3D HYDRODYNAMIC SWIMMING GOGGLES & SILICONE STRAP RIG
      // =======================================================================
      const goggleGroup = new THREE.Group();
      goggleGroup.scale.set(1.25, 1.25, 1.25);
      rootGroup.add(goggleGroup);

      // Sculpted Mannequin Head Preview (semi-transparent)
      const headMannequin = new THREE.Mesh(
        new THREE.SphereGeometry(0.68, 40, 32),
        new THREE.MeshStandardMaterial({
          color: 0x94a3b8,
          roughness: 0.35,
          metalness: 0.25,
          transparent: true,
          opacity: 0.38
        })
      );
      headMannequin.scale.set(0.86, 1.12, 0.95);
      headMannequin.position.set(0, 0.15, -0.18);
      goggleGroup.add(headMannequin);

      const mirrorLensMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(primaryColor),
        roughness: 0.06,
        metalness: 0.88,
        envMapIntensity: 1.5
      });

      [-0.32, 0.32].forEach(xPos => {
        // Silicone gasket frame
        const gasket = new THREE.Mesh(new THREE.TorusGeometry(0.24, 0.042, 20, 48), garmentMat);
        gasket.scale.set(1.25, 0.82, 0.9);
        gasket.position.set(xPos, 0.22, 0.44);
        gasket.rotation.y = xPos < 0 ? -0.18 : 0.18;
        goggleGroup.add(gasket);

        // Curved Hydrodynamic Mirror Lens
        const lens = new THREE.Mesh(new THREE.SphereGeometry(0.235, 32, 24, 0, Math.PI * 2, 0, Math.PI * 0.55), mirrorLensMat);
        lens.scale.set(1.25, 0.82, 0.55);
        lens.rotation.x = Math.PI / 2;
        lens.position.set(xPos, 0.22, 0.42);
        goggleGroup.add(lens);
      });

      // Ergonomic Nose Bridge
      const bridge = new THREE.Mesh(new THREE.TorusGeometry(0.09, 0.022, 12, 24, Math.PI), seamAccentMat);
      bridge.position.set(0, 0.21, 0.48);
      goggleGroup.add(bridge);

      // Twin Split Silicone Head Straps
      [-0.06, 0.06].forEach(yOff => {
        const strap = new THREE.Mesh(new THREE.TorusGeometry(0.64, 0.024, 16, 64, Math.PI * 1.65), garmentMat);
        strap.rotation.x = Math.PI / 2 + yOff * 0.6;
        strap.rotation.z = Math.PI * 0.68;
        strap.scale.set(0.92, 1.05, 1.0);
        strap.position.set(0, 0.22 + yOff, -0.14);
        goggleGroup.add(strap);
      });
    } else {
      // =======================================================================
      // 1. SCULPTED 3D ANATOMICAL MANNEQUIN (HEAD, NECK, TORSO, LEGS, ARMS)
      // =======================================================================
      const mannequinTorso = new THREE.Mesh(
        buildParametricTorsoGeometry(isMale, 0, geomType, false),
        mannequinMat
      );
      rootGroup.add(mannequinTorso);

      // Sculpted Mannequin Head & Jawline
      const headMesh = new THREE.Mesh(new THREE.SphereGeometry(0.21, 32, 28), mannequinMat);
      headMesh.scale.set(0.84, 1.14, 0.92);
      headMesh.position.set(0, 1.34, 0.02);
      rootGroup.add(headMesh);

      // Left & Right Sculpted Legs (Thighs to Calves)
      const hipX = isMale ? 0.19 : 0.20;
      [-1, 1].forEach(side => {
        const legGeo = buildLimbGeometry(
          -0.54,
          -1.36,
          side * hipX,
          side * (hipX * 0.86),
          isMale ? 0.195 : 0.19,
          0.115,
          0.94,
          0
        );
        rootGroup.add(new THREE.Mesh(legGeo, mannequinMat));
      });

      // Left & Right Sculpted Arms
      const shoulderX = isMale ? 0.48 : 0.42;
      [-1, 1].forEach(side => {
        const armGeo = buildLimbGeometry(
          0.86,
          0.02,
          side * shoulderX,
          side * (shoulderX + 0.16),
          isMale ? 0.115 : 0.098,
          0.068,
          0.92,
          0
        );
        rootGroup.add(new THREE.Mesh(armGeo, mannequinMat));

        // Smooth Shoulder Deltoid Cap
        const deltoid = new THREE.Mesh(new THREE.SphereGeometry(isMale ? 0.125 : 0.108, 24, 20), mannequinMat);
        deltoid.position.set(side * shoulderX, 0.87, 0);
        rootGroup.add(deltoid);
      });

      // =======================================================================
      // 2. CONTOURED 3D SWIMWEAR GARMENT SHELL + RAISED 3D SEAMS
      // =======================================================================
      const garmentTorsoGeo = buildParametricTorsoGeometry(isMale, 0.016, geomType, true);
      const garmentTorsoMesh = new THREE.Mesh(garmentTorsoGeo, garmentMat);
      rootGroup.add(garmentTorsoMesh);
      garmentMeshes.push(garmentTorsoMesh);

      const wireTorsoMesh = new THREE.Mesh(garmentTorsoGeo, wireframeMat);
      wireTorsoMesh.scale.set(1.003, 1.003, 1.003);
      rootGroup.add(wireTorsoMesh);
      wireMeshes.push(wireTorsoMesh);

      // Additional Garment Parts by Type
      if (geomType === "jammer_3d") {
        // 3D Jammer Shorts Legs + Contrasting Elastic Waistband
        [-1, 1].forEach(side => {
          const jammerLegGeo = buildLimbGeometry(
            -0.52,
            -1.08,
            side * hipX,
            side * (hipX * 0.90),
            0.195,
            0.145,
            0.94,
            0.015
          );
          const legMesh = new THREE.Mesh(jammerLegGeo, garmentMat);
          rootGroup.add(legMesh);
          garmentMeshes.push(legMesh);

          const legWire = new THREE.Mesh(jammerLegGeo, wireframeMat);
          rootGroup.add(legWire);
          wireMeshes.push(legWire);

          // 3D Silicone Leg Gripper Band above knee
          const hemBand = new THREE.Mesh(new THREE.TorusGeometry(0.155, 0.012, 12, 32), seamAccentMat);
          hemBand.rotation.x = Math.PI / 2;
          hemBand.position.set(side * (hipX * 0.90), -1.07, -0.02);
          rootGroup.add(hemBand);
        });

        // 3D Raised Waistband
        const waistBelt = new THREE.Mesh(new THREE.TorusGeometry(0.38, 0.018, 16, 48), seamAccentMat);
        waistBelt.rotation.x = Math.PI / 2;
        waistBelt.scale.set(1.04, 0.68, 1.0);
        waistBelt.position.set(0, -0.02, 0);
        rootGroup.add(waistBelt);
      } else if (geomType === "rashguard_3d") {
        // Full 3D Long Sleeves + Mock Collar + Front Zipper Track
        [-1, 1].forEach(side => {
          const sleeveGeo = buildLimbGeometry(
            0.87,
            0.08,
            side * shoulderX,
            side * (shoulderX + 0.15),
            0.102,
            0.072,
            0.92,
            0.014
          );
          const sleeveMesh = new THREE.Mesh(sleeveGeo, garmentMat);
          rootGroup.add(sleeveMesh);
          garmentMeshes.push(sleeveMesh);

          const sleeveCap = new THREE.Mesh(new THREE.SphereGeometry(0.118, 24, 20), garmentMat);
          sleeveCap.position.set(side * shoulderX, 0.87, 0);
          rootGroup.add(sleeveCap);
        });

        // 3D Mock-Neck Collar & Center Front Zipper Line
        const collar = new THREE.Mesh(new THREE.CylinderGeometry(0.165, 0.185, 0.11, 32, 1, true), seamAccentMat);
        collar.position.set(0, 1.07, 0);
        rootGroup.add(collar);
      } else if (geomType === "bikini_3d") {
        // Center Metallic Gold/Cyan Bikini Clasp Ring
        const centerClasp = new THREE.Mesh(new THREE.TorusGeometry(0.038, 0.009, 12, 24), seamAccentMat);
        centerClasp.position.set(0, 0.56, 0.29);
        rootGroup.add(centerClasp);
      }
    }

    // =========================================================================
    // 3. 3D ILLUMINATED WATER CAUSTICS & TURNTABLE STAGE PEDESTAL
    // =========================================================================
    const stageGroup = new THREE.Group();
    stageGroup.position.y = -1.44;
    rootGroup.add(stageGroup);

    const outerGlowRing = new THREE.Mesh(
      new THREE.TorusGeometry(1.18, 0.022, 16, 96),
      new THREE.MeshBasicMaterial({ color: 0x22d3ee })
    );
    outerGlowRing.rotation.x = Math.PI / 2;
    stageGroup.add(outerGlowRing);

    const innerWaterDisc = new THREE.Mesh(
      new THREE.CircleGeometry(1.16, 64),
      new THREE.MeshStandardMaterial({
        color: 0x083344,
        roughness: 0.15,
        metalness: 0.65,
        transparent: true,
        opacity: 0.65
      })
    );
    innerWaterDisc.rotation.x = -Math.PI / 2;
    innerWaterDisc.position.y = -0.01;
    stageGroup.add(innerWaterDisc);

    // Floating 3D Hydro Bubbles around the Mannequin
    const bubblesGroup = new THREE.Group();
    rootGroup.add(bubblesGroup);
    const bubbleGeo = new THREE.SphereGeometry(0.025, 12, 12);
    const bubbleMat = new THREE.MeshBasicMaterial({ color: 0x67e8f9, transparent: true, opacity: 0.45 });
    const bubbles = [];
    for (let i = 0; i < 18; i++) {
      const b = new THREE.Mesh(bubbleGeo, bubbleMat);
      const ang = (i / 18) * Math.PI * 2;
      const rad = 0.72 + (i % 3) * 0.18;
      b.position.set(Math.cos(ang) * rad, -1.1 + (i % 7) * 0.35, Math.sin(ang) * rad);
      bubblesGroup.add(b);
      bubbles.push({ mesh: b, speed: 0.004 + (i % 4) * 0.0015 });
    }

    // Viewer state & interactive pointer controls
    const state = {
      rotX: options.initialRotX !== undefined ? options.initialRotX : 8,
      rotY: options.initialRotY !== undefined ? options.initialRotY : -18,
      zoom: 1.0,
      scaleX: 1.0,
      scaleY: 1.0,
      autoRotate: options.autoRotate !== false,
      wireframe: false,
      isDragging: false,
      lastX: 0,
      lastY: 0,
      destroyed: false,
      animId: null
    };

    function applyTransforms() {
      rootGroup.rotation.y = (state.rotY * Math.PI) / 180;
      rootGroup.rotation.x = (state.rotX * Math.PI) / 180;
      rootGroup.scale.set(
        state.zoom * state.scaleX,
        state.zoom * state.scaleY,
        state.zoom * state.scaleX
      );
      if (typeof options.onTransformChange === "function") {
        options.onTransformChange(state);
      }
    }

    const onPointerDown = (e) => {
      state.isDragging = true;
      state.autoRotate = false;
      state.lastX = e.clientX;
      state.lastY = e.clientY;
    };
    const onPointerMove = (e) => {
      if (!state.isDragging) return;
      const dx = e.clientX - state.lastX;
      const dy = e.clientY - state.lastY;
      state.lastX = e.clientX;
      state.lastY = e.clientY;
      state.rotY += dx * 0.65;
      state.rotX = Math.max(-42, Math.min(42, state.rotX + dy * 0.42));
      applyTransforms();
    };
    const onPointerUp = () => {
      state.isDragging = false;
    };
    const onWheel = (e) => {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 0.07 : -0.07;
      state.zoom = Math.max(0.65, Math.min(1.65, state.zoom + delta));
      applyTransforms();
    };

    canvas.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });

    applyTransforms();

    function animate() {
      if (state.destroyed) return;
      state.animId = requestAnimationFrame(animate);
      if (state.autoRotate && !state.isDragging) {
        state.rotY += 0.42;
        applyTransforms();
      }
      // Animate floating 3D hydro bubbles
      bubbles.forEach(b => {
        b.mesh.position.y += b.speed;
        if (b.mesh.position.y > 1.35) b.mesh.position.y = -1.25;
      });
      renderer.render(scene, camera);
    }
    animate();

    const controller = {
      state,
      setColor(hex) {
        createFabricTextures(hex, "#22d3ee", productImgUrl, ({ diffTex, bumpTex }) => {
          garmentMat.color.set(hex);
          garmentMat.map = diffTex;
          garmentMat.bumpMap = bumpTex;
          garmentMat.needsUpdate = true;
        });
      },
      setLighting(presetId) {
        const presets = {
          "ocean-daylight": { amb: 0xe0f2fe, key: 0xffffff, fill: 0x38bdf8 },
          "ibiza-sunset": { amb: 0xffedd5, key: 0xfb923c, fill: 0xf43f5e },
          "neon-runway": { amb: 0xe9d5ff, key: 0xc084fc, fill: 0x22d3ee },
          "studio-pure": { amb: 0xffffff, key: 0xffffff, fill: 0xe2e8f0 }
        };
        const p = presets[presetId] || presets["ocean-daylight"];
        ambientLight.color.setHex(p.amb);
        keyLight.color.setHex(p.key);
        fillLight.color.setHex(p.fill);
      },
      setWireframe(enabled) {
        state.wireframe = enabled;
        wireframeMat.opacity = enabled ? 0.38 : 0.0;
      },
      setBodyScale(scaleX, scaleY) {
        state.scaleX = scaleX;
        state.scaleY = scaleY;
        applyTransforms();
      },
      setZoom(zoomVal) {
        state.zoom = zoomVal;
        applyTransforms();
      },
      setAutoRotate(flag) {
        state.autoRotate = flag;
      },
      resetCamera() {
        state.rotX = 8;
        state.rotY = -18;
        state.zoom = 1.0;
        applyTransforms();
      },
      destroy() {
        state.destroyed = true;
        if (state.animId) cancelAnimationFrame(state.animId);
        canvas.removeEventListener("pointerdown", onPointerDown);
        window.removeEventListener("pointermove", onPointerMove);
        window.removeEventListener("pointerup", onPointerUp);
        canvas.removeEventListener("wheel", onWheel);
        try {
          renderer.dispose();
        } catch (e) {}
        activeViewers.delete(canvasId);
      }
    };

    activeViewers.set(canvasId, controller);
    return controller;
  }

  window.Soobin3DEngine = {
    mount: mountSwimwear3DViewer,
    getViewer: (id) => activeViewers.get(id)
  };
})();

