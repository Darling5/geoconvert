// geoconvert 3D 预览与三轴调整（离线 Cesium，无外网）
// 移植自主系统 www/src/lib/api/model_gizmo.ts + model_transforms.ts + BuildingModels.svelte
// 数学约定与主系统一致：A = T(pivot+t)×S×R×T(-pivot)（ENU 局部系），
// 实时 modelMatrix = R×A×R⁻¹，保存烘焙新 root.transform = R×A。
(function () {
  'use strict';
  let viewer = null, tileset = null, gizmo = null;
  let curDir = '', pivot = [0, 0, 0];
  let t = { x: 0, y: 0, z: 0, heading: 0, pitch: 0, roll: 0, sx: 1, sy: 1, sz: 1 };
  let dragStartT = null;
  let engineLoading = false;

  const $ = (s) => document.querySelector(s);

  // ===== 变换数学（model_transforms.ts 移植）=====

  function isZero(tv) {
    return !tv.x && !tv.y && !tv.z && !tv.heading && !tv.pitch && !tv.roll &&
      (tv.sx ?? 1) === 1 && (tv.sy ?? 1) === 1 && (tv.sz ?? 1) === 1;
  }

  function buildAdjustMatrix(tv, pv) {
    const M4 = Cesium.Matrix4;
    const rot = Cesium.Matrix3.fromHeadingPitchRoll(new Cesium.HeadingPitchRoll(
      Cesium.Math.toRadians(tv.heading || 0),
      Cesium.Math.toRadians(tv.pitch || 0),
      Cesium.Math.toRadians(tv.roll || 0)));
    const p = [pv[0] || 0, pv[1] || 0, pv[2] || 0];
    const S = M4.fromScale(new Cesium.Cartesian3(tv.sx ?? 1, tv.sy ?? 1, tv.sz ?? 1));
    return M4.multiply(
      M4.fromTranslation(new Cesium.Cartesian3(p[0] + (tv.x || 0), p[1] + (tv.y || 0), p[2] + (tv.z || 0))),
      M4.multiply(S,
        M4.multiply(
          M4.fromRotationTranslation(rot, Cesium.Cartesian3.ZERO),
          M4.fromTranslation(new Cesium.Cartesian3(-p[0], -p[1], -p[2])),
          new M4()),
        new M4()),
      new M4());
  }

  function applyTransform() {
    if (!tileset || !tileset.root) return;
    if (isZero(t)) {
      tileset.modelMatrix = Cesium.Matrix4.IDENTITY.clone();
    } else {
      const R = tileset.root.transform;
      const A = buildAdjustMatrix(t, pivot);
      const Rin = Cesium.Matrix4.inverse(R, new Cesium.Matrix4());
      tileset.modelMatrix = Cesium.Matrix4.multiply(
        R, Cesium.Matrix4.multiply(A, Rin, new Cesium.Matrix4()), new Cesium.Matrix4());
    }
    syncInputs();
  }

  function bakedMatrix() {
    const R = tileset.root.transform;
    return Cesium.Matrix4.toArray(
      Cesium.Matrix4.multiply(R, buildAdjustMatrix(t, pivot), new Cesium.Matrix4()));
  }

  function axisColENU(axis) {
    const e = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] }[axis];
    const A = buildAdjustMatrix(t, pivot);
    const v = Cesium.Matrix4.multiplyByPointAsVector(A,
      new Cesium.Cartesian3(e[0], e[1], e[2]), new Cesium.Cartesian3());
    return Cesium.Cartesian3.normalize(v, v);
  }

  // ===== 模型透明度（BuildingModels.svelte applyOpacity 移植）=====
  // 作用于原模型本体（Cesium3DTileStyle color 调制 alpha），不建副本；
  // 100% 时置回 null 恢复原样；loadTileset 重建 tileset 后需重应用。

  let opacityPct = 100;

  function applyOpacity() {
    if (!tileset) return;
    if (opacityPct >= 100) {
      tileset.style = null;
    } else {
      tileset.style = new Cesium.Cesium3DTileStyle({
        color: `color('white', ${(opacityPct / 100).toFixed(2)})`,
      });
    }
  }

  // ===== Gizmo（model_gizmo.ts 移植）=====

  const TRANSLATE_AXES = {
    x: { dir: 'east', color: () => Cesium.Color.fromCssColorString('#ff4d4d') },
    y: { dir: 'north', color: () => Cesium.Color.fromCssColorString('#4dff77') },
    z: { dir: 'up', color: () => Cesium.Color.fromCssColorString('#4d9fff') },
  };
  const ROTATE_RINGS = {
    heading: { normal: 'up', u: 'east', v: 'north', sign: -1, color: () => Cesium.Color.fromCssColorString('#4d9fff') },
    pitch: { normal: 'north', u: 'east', v: 'up', sign: 1, color: () => Cesium.Color.fromCssColorString('#4dff77') },
    roll: { normal: 'east', u: 'north', v: 'up', sign: 1, color: () => Cesium.Color.fromCssColorString('#ff4d4d') },
  };
  const PLANE_HANDLES = {
    xy: { axes: ['x', 'y'], u: 'east', v: 'north', color: () => Cesium.Color.fromCssColorString('#ffe14d') },
    xz: { axes: ['x', 'z'], u: 'east', v: 'up', color: () => Cesium.Color.fromCssColorString('#ff4dd2') },
    yz: { axes: ['y', 'z'], u: 'north', v: 'up', color: () => Cesium.Color.fromCssColorString('#4dfff0') },
  };
  const SCALE_HANDLES = {
    sx: { dir: 'east', color: () => Cesium.Color.fromCssColorString('#ff4d4d') },
    sy: { dir: 'north', color: () => Cesium.Color.fromCssColorString('#4dff77') },
    sz: { dir: 'up', color: () => Cesium.Color.fromCssColorString('#4d9fff') },
  };
  const SCALE_BOX_T = 0.67, SCALE_BOX_H = 0.055;
  const CAM_FLAGS = ['enableRotate', 'enableTranslate', 'enableZoom', 'enableTilt', 'enableLook'];

  function wrapPI(a) {
    while (a > Math.PI) a -= 2 * Math.PI;
    while (a < -Math.PI) a += 2 * Math.PI;
    return a;
  }

  class ModelGizmo {
    constructor(opts) {
      this.opts = opts;
      this.viewer = opts.viewer;
      this.scene = opts.viewer.scene;
      this.entities = [];
      this.entityInfos = [];
      this.parent = null;
      this.downListener = null; this.moveListener = null; this.upListener = null;
      this.hoverListener = null; this.wheelListener = null;
      this.hoverAxis = null;
      this.drag = null;
      this.shown = true;
      this.baseCamFlags = {};
      for (const f of CAM_FLAGS) this.baseCamFlags[f] = this.scene.screenSpaceCameraController[f];
      this._buildEntities();
      this._bindEvents();
    }

    setShow(v) {
      this.shown = v;
      for (const e of this.entities) e.show = v;
      if (!v) { this._endDrag(); this._setHover(null); }
    }

    destroy() {
      this._endDrag();
      this._setHover(null);
      this._applyCamFlags();
      if (this.parent) {
        this.parent.removeEventListener('pointerdown', this.downListener, { capture: true });
        this.parent.removeEventListener('wheel', this.wheelListener, { capture: true });
      }
      window.removeEventListener('pointermove', this.moveListener, { capture: true });
      window.removeEventListener('pointerup', this.upListener, { capture: true });
      this.viewer.canvas.removeEventListener('pointermove', this.hoverListener);
      this.parent = null;
      for (const e of this.entities) this.viewer.entities.remove(e);
      this.entities = [];
    }

    _curLen() {
      const p = this.opts.getPlacement();
      if (!p) return 30;
      const dist = Cesium.Cartesian3.distance(this.viewer.camera.positionWC, p.pivotWorld);
      return Math.max(10, Math.min(800, dist * 0.12));
    }

    _buildEntities() {
      const self = this;
      const mkLine = (positionsFn, color, width, handle, suffix) => {
        const e = this.viewer.entities.add({
          id: `__gizmo_${handle}_${suffix}`,
          polyline: { positions: new Cesium.CallbackProperty(positionsFn, false), width, material: color },
        });
        this.entities.push(e);
        this.entityInfos.push({ e, kind: 'line', handle, width, color });
        return e;
      };
      const mkPoly = (positionsFn, color, handle, baseAlpha, hoverAlpha, outline) => {
        const e = this.viewer.entities.add({
          id: `__gizmo_${handle}_poly`,
          polygon: {
            hierarchy: new Cesium.CallbackProperty(() => new Cesium.PolygonHierarchy(positionsFn()), false),
            material: new Cesium.ColorMaterialProperty(color.withAlpha(baseAlpha)),
            // 不加 perPositionHeight，polygon 会丢掉 Z 坐标贴地渲染（方块不跟轴的根因）
            perPositionHeight: true,
            outline: !!outline,
            outlineColor: outline ? color : undefined,
          },
        });
        this.entities.push(e);
        this.entityInfos.push({ e, kind: 'poly', handle, width: 0, color, baseAlpha, hoverAlpha });
        return e;
      };

      for (const key of ['x', 'y', 'z']) {
        const info = TRANSLATE_AXES[key];
        const line = (tip) => () => {
          if (!self.shown) return [];
          const p = self.opts.getPlacement();
          if (!p) return [];
          const len = self._curLen();
          const dir = Cesium.Cartesian3.normalize(p[info.dir], new Cesium.Cartesian3());
          const start = p.pivotWorld;
          const tipPos = Cesium.Cartesian3.add(start,
            Cesium.Cartesian3.multiplyByScalar(dir, len, new Cesium.Cartesian3()), new Cesium.Cartesian3());
          if (tip) return [start, tipPos];
          // 箭头头部两撇；dir 与视线平行时（俯视的 Z 轴）cross≈0，换用最不平行的 ENU 轴求垂直向量
          const camDir = self.viewer.camera.directionWC;
          let perp = Cesium.Cartesian3.cross(dir, camDir, new Cesium.Cartesian3());
          if (Cesium.Cartesian3.magnitude(perp) < 0.1) {
            for (const ref of [p.east, p.north, p.up]) {
              const cr = Cesium.Cartesian3.cross(dir, ref, new Cesium.Cartesian3());
              if (Cesium.Cartesian3.magnitude(cr) > Cesium.Cartesian3.magnitude(perp)) perp = cr;
            }
          }
          perp = Cesium.Cartesian3.normalize(perp, new Cesium.Cartesian3());
          const hl = len * 0.18;
          const back = Cesium.Cartesian3.multiplyByScalar(dir, -hl, new Cesium.Cartesian3());
          const h1 = Cesium.Cartesian3.add(tipPos,
            Cesium.Cartesian3.add(back, Cesium.Cartesian3.multiplyByScalar(perp, hl * 0.6, new Cesium.Cartesian3()), new Cesium.Cartesian3()), new Cesium.Cartesian3());
          const h2 = Cesium.Cartesian3.add(tipPos,
            Cesium.Cartesian3.add(back, Cesium.Cartesian3.multiplyByScalar(perp, -hl * 0.6, new Cesium.Cartesian3()), new Cesium.Cartesian3()), new Cesium.Cartesian3());
          return [tipPos, h1, tipPos, h2];
        };
        mkLine(line(true), info.color().withAlpha(0.95), 8, key, 'main');
        mkLine(line(false), info.color().withAlpha(0.95), 5, key, 'head');
      }

      for (const key of ['heading', 'pitch', 'roll']) {
        const info = ROTATE_RINGS[key];
        const ring = () => {
          if (!self.shown) return [];
          const p = self.opts.getPlacement();
          if (!p) return [];
          const r = self._curLen() * 0.55;
          const u = Cesium.Cartesian3.normalize(p[info.u], new Cesium.Cartesian3());
          const v = Cesium.Cartesian3.normalize(p[info.v], new Cesium.Cartesian3());
          const pts = [];
          for (let i = 0; i <= 64; i++) {
            const a = (i / 64) * Math.PI * 2;
            pts.push(Cesium.Cartesian3.add(p.pivotWorld,
              Cesium.Cartesian3.add(
                Cesium.Cartesian3.multiplyByScalar(u, Math.cos(a) * r, new Cesium.Cartesian3()),
                Cesium.Cartesian3.multiplyByScalar(v, Math.sin(a) * r, new Cesium.Cartesian3()),
                new Cesium.Cartesian3()),
              new Cesium.Cartesian3()));
          }
          return pts;
        };
        mkLine(ring, info.color().withAlpha(0.55), 4, key, 'ring');
      }

      for (const key of ['xy', 'xz', 'yz']) {
        const info = PLANE_HANDLES[key];
        const quad = () => {
          const p = self.opts.getPlacement();
          if (!p) return [];
          const len = self._curLen();
          const u = Cesium.Cartesian3.normalize(p[info.u], new Cesium.Cartesian3());
          const v = Cesium.Cartesian3.normalize(p[info.v], new Cesium.Cartesian3());
          const a0 = len * 0.22, a1 = len * 0.52;
          const corner = (au, av) => Cesium.Cartesian3.add(p.pivotWorld,
            Cesium.Cartesian3.add(
              Cesium.Cartesian3.multiplyByScalar(u, au, new Cesium.Cartesian3()),
              Cesium.Cartesian3.multiplyByScalar(v, av, new Cesium.Cartesian3()),
              new Cesium.Cartesian3()),
            new Cesium.Cartesian3());
          return [corner(a0, a0), corner(a1, a0), corner(a1, a1), corner(a0, a1)];
        };
        mkPoly(quad, info.color(), key, 0.28, 0.45, false);
      }

      for (const key of ['sx', 'sy', 'sz']) {
        const info = SCALE_HANDLES[key];
        const box = () => {
          if (!self.shown) return [];
          const p = self.opts.getPlacement();
          if (!p) return [];
          const len = self._curLen();
          const dir = Cesium.Cartesian3.normalize(p[info.dir], new Cesium.Cartesian3());
          const center = Cesium.Cartesian3.add(p.pivotWorld,
            Cesium.Cartesian3.multiplyByScalar(dir, len * SCALE_BOX_T, new Cesium.Cartesian3()), new Cesium.Cartesian3());
          const cam = self.viewer.camera;
          const h = len * SCALE_BOX_H;
          const corner = (su, sv) => Cesium.Cartesian3.add(center,
            Cesium.Cartesian3.add(
              Cesium.Cartesian3.multiplyByScalar(cam.rightWC, su * h, new Cesium.Cartesian3()),
              Cesium.Cartesian3.multiplyByScalar(cam.upWC, sv * h, new Cesium.Cartesian3()),
              new Cesium.Cartesian3()),
            new Cesium.Cartesian3());
          return [corner(1, 1), corner(-1, 1), corner(-1, -1), corner(1, -1)];
        };
        mkPoly(box, info.color(), key, 0.55, 0.85, true);
      }
    }

    _bindEvents() {
      const canvas = this.viewer.canvas;
      const parent = canvas.parentElement || canvas;
      this.parent = parent;

      this.downListener = (ev) => {
        if (!this.shown || this.drag) return;
        const pos = this._clientToCanvas(ev);
        if (pos && this._tryStartDrag(pos)) {
          ev.preventDefault();
          ev.stopPropagation();
          try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
        }
      };
      parent.addEventListener('pointerdown', this.downListener, { capture: true, passive: false });

      this.moveListener = (ev) => {
        if (this.drag) {
          ev.preventDefault();
          ev.stopPropagation();
          this._onDragMove(this._clientToCanvas(ev));
        }
      };
      window.addEventListener('pointermove', this.moveListener, { capture: true, passive: false });

      this.upListener = (ev) => {
        if (this.drag) {
          ev.preventDefault();
          ev.stopPropagation();
          this._endDrag();
        }
      };
      window.addEventListener('pointerup', this.upListener, { capture: true, passive: false });

      this.hoverListener = (ev) => {
        if (this.drag) return;
        const pos = this._clientToCanvas(ev);
        const handle = pos ? this._pickHandle(pos) : null;
        if (handle !== this.hoverAxis) this._setHover(handle);
      };
      canvas.addEventListener('pointermove', this.hoverListener);

      this.wheelListener = (e) => {
        if (this.drag || !this.shown) return;
        const handle = this.hoverAxis;
        if (!handle || handle === 'xy' || handle === 'xz' || handle === 'yz') return;
        e.preventDefault();
        e.stopPropagation();
        const amount = 0.01 * (e.deltaY < 0 ? 1 : -1);
        this.opts.onNudge(handle, amount);
      };
      parent.addEventListener('wheel', this.wheelListener, { capture: true, passive: false });
    }

    _clientToCanvas(ev) {
      const rect = this.viewer.canvas.getBoundingClientRect();
      return new Cesium.Cartesian2(ev.clientX - rect.left, ev.clientY - rect.top);
    }

    _tryStartDrag(pos) {
      const handle = this._pickHandle(pos);
      if (!handle) return false;
      const p = this.opts.getPlacement();
      if (!p) return false;
      const cam = this.viewer.camera;
      let kind, plane, u, v, grazing = false;
      if (handle === 'x' || handle === 'y' || handle === 'z') {
        kind = 'translate';
        const axisVec = Cesium.Cartesian3.normalize(p[TRANSLATE_AXES[handle].dir], new Cesium.Cartesian3());
        // 求交平面取屏幕平行平面（法向=视线），箭头近屏幕中心时求交稳定
        const n = Cesium.Cartesian3.normalize(cam.directionWC, new Cesium.Cartesian3());
        plane = Cesium.Plane.fromPointNormal(p.pivotWorld, n);
        u = axisVec; v = n;
      } else if (handle === 'xy' || handle === 'xz' || handle === 'yz') {
        kind = 'plane';
        const info = PLANE_HANDLES[handle];
        u = Cesium.Cartesian3.normalize(p[info.u], new Cesium.Cartesian3());
        v = Cesium.Cartesian3.normalize(p[info.v], new Cesium.Cartesian3());
        let n = Cesium.Cartesian3.cross(u, v, new Cesium.Cartesian3());
        if (Math.abs(Cesium.Cartesian3.dot(n, cam.directionWC)) < 0.15) n = cam.directionWC;
        n = Cesium.Cartesian3.normalize(n, new Cesium.Cartesian3());
        plane = Cesium.Plane.fromPointNormal(p.pivotWorld, n);
      } else if (handle === 'sx' || handle === 'sy' || handle === 'sz') {
        kind = 'scale';
        const info = SCALE_HANDLES[handle];
        u = Cesium.Cartesian3.normalize(p[info.dir], new Cesium.Cartesian3());
        const n = Cesium.Cartesian3.normalize(cam.directionWC, new Cesium.Cartesian3());
        const anchor = Cesium.Cartesian3.add(p.pivotWorld,
          Cesium.Cartesian3.multiplyByScalar(u, this._curLen() * SCALE_BOX_T, new Cesium.Cartesian3()), new Cesium.Cartesian3());
        plane = Cesium.Plane.fromPointNormal(anchor, n);
        v = n;
        this.drag = { handle, kind, plane, origin: Cesium.Cartesian3.clone(p.pivotWorld), anchor, u, v };
        const start = this._rayPlane(pos, plane);
        if (!start) { this.drag = null; return false; }
        this.drag.s0 = this._proj(start, this.drag.origin, u);
        this.opts.onDragStart(handle);
        this._applyCamFlags();
        this.viewer.canvas.style.cursor = 'grabbing';
        return true;
      } else {
        kind = 'rotate';
        const info = ROTATE_RINGS[handle];
        const axisVec = Cesium.Cartesian3.normalize(p[info.normal], new Cesium.Cartesian3());
        // 旋转环掠射时改用屏幕角度模式，避免 ray-plane 无交
        grazing = Math.abs(Cesium.Cartesian3.dot(axisVec, cam.directionWC)) < 0.15;
        plane = Cesium.Plane.fromPointNormal(p.pivotWorld, axisVec);
        u = Cesium.Cartesian3.normalize(p[info.u], new Cesium.Cartesian3());
        v = Cesium.Cartesian3.normalize(p[info.v], new Cesium.Cartesian3());
      }
      const start = this._rayPlane(pos, plane);
      if (!start && !grazing) return false;
      const origin = Cesium.Cartesian3.clone(p.pivotWorld);
      this.drag = { handle, kind, plane, origin, u, v, grazing };
      if (kind === 'translate') {
        this.drag.s0 = this._proj(start, origin, u);
      } else if (kind === 'plane') {
        this.drag.s0u = this._proj(start, origin, u);
        this.drag.s0v = this._proj(start, origin, v);
      } else if (grazing) {
        const c0 = this.scene.cartesianToCanvasCoordinates(origin, new Cesium.Cartesian2());
        this.drag.c0 = c0 ? { x: c0.x, y: c0.y } : null;
        this.drag.p0 = pos;
        this.drag.acc = 0;
        this.drag.prevA = this.drag.c0 ? Math.atan2(pos.y - this.drag.c0.y, pos.x - this.drag.c0.x) : 0;
      } else {
        this.drag.acc = 0;
        this.drag.prevA = this._angleOnPlane(start, origin, u, v);
      }
      this.opts.onDragStart(handle);
      this._applyCamFlags();
      this.viewer.canvas.style.cursor = 'grabbing';
      return true;
    }

    _onDragMove(pos) {
      if (!pos || !this.drag) return;
      const { origin, u, v } = this.drag;
      if (this.drag.kind === 'translate') {
        const hit = this._rayPlane(pos, this.drag.plane);
        if (!hit) return;
        const s = this._proj(hit, origin, u);
        this.opts.onDrag(this.drag.handle, s - this.drag.s0);
      } else if (this.drag.kind === 'plane') {
        const hit = this._rayPlane(pos, this.drag.plane);
        if (!hit) return;
        const info = PLANE_HANDLES[this.drag.handle];
        const du = this._proj(hit, origin, u) - this.drag.s0u;
        const dv = this._proj(hit, origin, v) - this.drag.s0v;
        this.opts.onPlaneDrag(info.axes, du, dv);
      } else if (this.drag.kind === 'scale') {
        const hit = this._rayPlane(pos, this.drag.plane);
        if (!hit) return;
        const s = this._proj(hit, origin, u);
        this.opts.onScaleDrag(this.drag.handle, s / this.drag.s0);
      } else if (this.drag.grazing && this.drag.c0) {
        const a = Math.atan2(pos.y - this.drag.c0.y, pos.x - this.drag.c0.x);
        this.drag.acc = (this.drag.acc || 0) + wrapPI(a - this.drag.prevA);
        this.drag.prevA = a;
        const sign = ROTATE_RINGS[this.drag.handle].sign;
        this.opts.onDrag(this.drag.handle, sign * Cesium.Math.toDegrees(this.drag.acc));
      } else {
        const hit = this._rayPlane(pos, this.drag.plane);
        if (!hit) return;
        const a = this._angleOnPlane(hit, origin, u, v);
        this.drag.acc = (this.drag.acc || 0) + wrapPI(a - this.drag.prevA);
        this.drag.prevA = a;
        const sign = ROTATE_RINGS[this.drag.handle].sign;
        this.opts.onDrag(this.drag.handle, sign * Cesium.Math.toDegrees(this.drag.acc));
      }
    }

    _endDrag() {
      if (!this.drag) return;
      this.drag = null;
      this._applyCamFlags();
      this.viewer.canvas.style.cursor = '';
    }

    // 屏幕空间命中测试：把箭头/圆环/平面方块投影到画布像素做 2D 距离判定（不依赖 scene.pick）
    _pickHandle(pos) {
      if (!this.shown) return null;
      const p = this.opts.getPlacement();
      if (!p) return null;
      const c2s = (world) => {
        const r = this.scene.cartesianToCanvasCoordinates(world, new Cesium.Cartesian2());
        return r ? { x: r.x, y: r.y } : null;
      };
      const center = c2s(p.pivotWorld);
      if (!center) return null;
      const len = this._curLen();

      const segDist = (px, py, a, b) => {
        const dx = b.x - a.x, dy = b.y - a.y;
        const l2 = dx * dx + dy * dy;
        let tt = l2 > 0 ? ((px - a.x) * dx + (py - a.y) * dy) / l2 : 0;
        tt = Math.max(0, Math.min(1, tt));
        return Math.hypot(px - (a.x + tt * dx), py - (a.y + tt * dy));
      };

      // 平面方块优先（射线与 3D 四边形求交，掠射视角下不会误命中箭头）
      const ray = this.viewer.camera.getPickRay(pos);
      if (ray) {
        const slack = len * 0.03;
        for (const key of ['xy', 'xz', 'yz']) {
          const info = PLANE_HANDLES[key];
          const u = Cesium.Cartesian3.normalize(p[info.u], new Cesium.Cartesian3());
          const v = Cesium.Cartesian3.normalize(p[info.v], new Cesium.Cartesian3());
          const n = Cesium.Cartesian3.normalize(
            Cesium.Cartesian3.cross(u, v, new Cesium.Cartesian3()), new Cesium.Cartesian3());
          const hit = Cesium.IntersectionTests.rayPlane(
            ray, Cesium.Plane.fromPointNormal(p.pivotWorld, n), new Cesium.Cartesian3());
          if (!hit) continue;
          const d = Cesium.Cartesian3.subtract(hit, p.pivotWorld, new Cesium.Cartesian3());
          const du = Cesium.Cartesian3.dot(d, u);
          const dv = Cesium.Cartesian3.dot(d, v);
          const a0 = len * 0.22 - slack, a1 = len * 0.52 + slack;
          if (du >= a0 && du <= a1 && dv >= a0 && dv <= a1) return key;
        }
      }

      // 缩放方块：屏幕半径判定（最小 9px 容差）
      for (const key of ['sx', 'sy', 'sz']) {
        const info = SCALE_HANDLES[key];
        const dir = Cesium.Cartesian3.normalize(p[info.dir], new Cesium.Cartesian3());
        const boxCenter = Cesium.Cartesian3.add(p.pivotWorld,
          Cesium.Cartesian3.multiplyByScalar(dir, len * SCALE_BOX_T, new Cesium.Cartesian3()), new Cesium.Cartesian3());
        const c = c2s(boxCenter);
        if (!c) continue;
        const h = len * SCALE_BOX_H;
        const cam = this.viewer.camera;
        const cEdge = c2s(Cesium.Cartesian3.add(boxCenter,
          Cesium.Cartesian3.multiplyByScalar(cam.rightWC, h, new Cesium.Cartesian3()), new Cesium.Cartesian3()));
        if (!cEdge) continue;
        const radius = Math.max(Math.hypot(cEdge.x - c.x, cEdge.y - c.y), 9);
        if (Math.hypot(pos.x - c.x, pos.y - c.y) <= radius) return key;
      }

      const THRESH = 12;
      let best = null;
      let bestDist = THRESH;

      for (const key of ['x', 'y', 'z']) {
        const info = TRANSLATE_AXES[key];
        const dir = Cesium.Cartesian3.normalize(p[info.dir], new Cesium.Cartesian3());
        const tip = c2s(Cesium.Cartesian3.add(p.pivotWorld,
          Cesium.Cartesian3.multiplyByScalar(dir, len, new Cesium.Cartesian3()), new Cesium.Cartesian3()));
        if (!tip) continue;
        const d = segDist(pos.x, pos.y, center, tip);
        if (d < bestDist) { bestDist = d; best = key; }
      }

      for (const key of ['heading', 'pitch', 'roll']) {
        const info = ROTATE_RINGS[key];
        const u = Cesium.Cartesian3.normalize(p[info.u], new Cesium.Cartesian3());
        const v = Cesium.Cartesian3.normalize(p[info.v], new Cesium.Cartesian3());
        const r = len * 0.55;
        let prev = null;
        for (let i = 0; i <= 48; i++) {
          const a = (i / 48) * Math.PI * 2;
          const w = Cesium.Cartesian3.add(p.pivotWorld,
            Cesium.Cartesian3.add(
              Cesium.Cartesian3.multiplyByScalar(u, Math.cos(a) * r, new Cesium.Cartesian3()),
              Cesium.Cartesian3.multiplyByScalar(v, Math.sin(a) * r, new Cesium.Cartesian3()),
              new Cesium.Cartesian3()),
            new Cesium.Cartesian3());
          const cur = c2s(w);
          if (cur && prev) {
            const d = segDist(pos.x, pos.y, prev, cur);
            if (d < bestDist) { bestDist = d; best = key; }
          }
          prev = cur;
        }
      }
      return best;
    }

    _setHover(handle) {
      for (const info of this.entityInfos) {
        const active = handle && info.handle === handle;
        if (info.kind === 'line') {
          const isRing = info.handle === 'heading' || info.handle === 'pitch' || info.handle === 'roll';
          if (active) {
            info.e.polyline.material.color = Cesium.Color.WHITE.withAlpha(0.95);
            info.e.polyline.width = info.width + 4;
          } else {
            info.e.polyline.material.color = info.color.withAlpha(isRing ? 0.55 : 0.95);
            info.e.polyline.width = info.width;
          }
        } else if (active) {
          info.e.polygon.material.color = Cesium.Color.WHITE.withAlpha(info.hoverAlpha ?? 0.45);
        } else {
          info.e.polygon.material.color = info.color.withAlpha(info.baseAlpha ?? 0.28);
        }
      }
      this.hoverAxis = handle;
      this._applyCamFlags();
      this.viewer.canvas.style.cursor = handle ? 'grab' : '';
    }

    _applyCamFlags() {
      const ssc = this.scene.screenSpaceCameraController;
      const h = this.hoverAxis;
      const planeHover = h === 'xy' || h === 'xz' || h === 'yz';
      for (const f of CAM_FLAGS) {
        let v = this.baseCamFlags[f];
        if (this.drag) v = false;
        else if (h && !planeHover && f === 'enableZoom') v = false;
        ssc[f] = v;
      }
    }

    _rayPlane(windowPos, plane) {
      const ray = this.viewer.camera.getPickRay(windowPos);
      if (!ray) return null;
      return Cesium.IntersectionTests.rayPlane(ray, plane, new Cesium.Cartesian3());
    }

    _proj(p, origin, dir) {
      const d = Cesium.Cartesian3.subtract(p, origin, new Cesium.Cartesian3());
      return Cesium.Cartesian3.dot(d, dir);
    }

    _angleOnPlane(p, origin, u, v) {
      const d = Cesium.Cartesian3.subtract(p, origin, new Cesium.Cartesian3());
      return Math.atan2(Cesium.Cartesian3.dot(d, v), Cesium.Cartesian3.dot(d, u));
    }
  }

  // ===== UI 胶水 =====

  function round2(v) { return Math.round(v * 100) / 100; }

  function clampParam(axis, v) {
    if (axis === 'sx' || axis === 'sy' || axis === 'sz') return Math.max(0.01, Math.min(20, v));
    if (axis === 'x' || axis === 'y' || axis === 'z') return v;  // 平移不设限（同 Cesium ion）
    let w = ((v + 180) % 360 + 360) % 360 - 180;
    if (w === -180) w = 180;
    return w;
  }

  function syncInputs() {
    for (const k of Object.keys(t)) {
      const el = $('#pv-' + k);
      if (el && document.activeElement !== el) el.value = t[k];
    }
    const su = $('#pv-su');
    if (su && document.activeElement !== su) {
      su.value = (t.sx === t.sy && t.sy === t.sz) ? t.sx
        : Math.round(((t.sx + t.sy + t.sz) / 3) * 100) / 100;
    }
  }

  function createGizmo() {
    if (gizmo) { gizmo.destroy(); gizmo = null; }
    if (!tileset) return;
    try {
      // 轴跟随模型当前姿态（同 Cesium ion：旋转后箭头/圆环/方块与模型一起转）
      gizmo = new ModelGizmo({
        viewer,
        getPlacement: () => {
          if (!tileset || !tileset.root) return null;
          const R = tileset.root.transform;
          const full = Cesium.Matrix4.multiply(tileset.modelMatrix, R, new Cesium.Matrix4());
          const pivotWorld = Cesium.Matrix4.multiplyByPoint(full,
            new Cesium.Cartesian3(pivot[0] || 0, pivot[1] || 0, pivot[2] || 0), new Cesium.Cartesian3());
          const east = Cesium.Matrix4.multiplyByPointAsVector(full, new Cesium.Cartesian3(1, 0, 0), new Cesium.Cartesian3());
          const north = Cesium.Matrix4.multiplyByPointAsVector(full, new Cesium.Cartesian3(0, 1, 0), new Cesium.Cartesian3());
          const up = Cesium.Matrix4.multiplyByPointAsVector(full, new Cesium.Cartesian3(0, 0, 1), new Cesium.Cartesian3());
          return { pivotWorld, east, north, up };
        },
        onDragStart: () => { dragStartT = { ...t }; },
        onDrag: (axis, delta) => {
          if (!dragStartT) return;
          if (axis === 'x' || axis === 'y' || axis === 'z') {
            // 拖拽增量沿模型当前轴方向，换算回 ENU 平移分量（箭头指哪模型往哪动）
            const col = axisColENU(axis);
            t = {
              ...t,
              x: round2(dragStartT.x + delta * col.x),
              y: round2(dragStartT.y + delta * col.y),
              z: round2(dragStartT.z + delta * col.z),
            };
          } else {
            t = { ...t, [axis]: round2(clampParam(axis, dragStartT[axis] + delta)) };
          }
          applyTransform();
        },
        onPlaneDrag: (axes, du, dv) => {
          if (!dragStartT) return;
          const ca = axisColENU(axes[0]), cb = axisColENU(axes[1]);
          t = {
            ...t,
            x: round2(dragStartT.x + du * ca.x + dv * cb.x),
            y: round2(dragStartT.y + du * ca.y + dv * cb.y),
            z: round2(dragStartT.z + du * ca.z + dv * cb.z),
          };
          applyTransform();
        },
        onScaleDrag: (axis, factor) => {
          if (!dragStartT) return;
          t = { ...t, [axis]: round2(clampParam(axis, (dragStartT[axis] ?? 1) * factor)) };
          applyTransform();
        },
        onNudge: (axis, amount) => {
          t = { ...t, [axis]: round2(clampParam(axis, (t[axis] ?? (axis.startsWith('s') ? 1 : 0)) + amount)) };
          applyTransform();
        },
      });
      gizmo.setShow($('#pv-show').checked);
    } catch (e) {
      pvStatus('调整轴创建失败：' + e, 'err');
      console.error('[gizmo]', e);
    }
  }

  function pvStatus(msg, cls) {
    const el = $('#pv-status');
    el.textContent = msg;
    el.className = cls || '';
  }

  function b64url(s) {
    return btoa(unescape(encodeURIComponent(s)))
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function loadScript(src) {
    return new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = res;
      s.onerror = () => rej(new Error('脚本加载失败：' + src));
      document.head.appendChild(s);
    });
  }

  async function ensureEngine() {
    if (viewer) return;
    if (engineLoading) throw new Error('引擎加载中，请稍候');
    engineLoading = true;
    try {
      if (!window.Cesium) {
        window.CESIUM_BASE_URL = new URL('cesium/', document.baseURI).href;
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'cesium/Widgets/widgets.css';
        document.head.appendChild(link);
        await loadScript('cesium/Cesium.js');
      }
      const credit = document.createElement('div');
      credit.style.display = 'none';
      document.body.appendChild(credit);
      viewer = new Cesium.Viewer($('#pv-viewer'), {
        animation: false, timeline: false, baseLayerPicker: false, geocoder: false,
        homeButton: false, sceneModePicker: false, navigationHelpButton: false,
        fullscreenButton: false, infoBox: false, selectionIndicator: false,
        baseLayer: Cesium.ImageryLayer.fromProviderAsync(
          Cesium.TileMapServiceImageryProvider.fromUrl(
            Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII'))),
        creditContainer: credit,
      });
      // 天地图 key 从 config.json 读取（界面「3D 预览」页可填，tianditu.gov.cn 免费申请）
      let tdtKey = '';
      try {
        const r = await fetch('api/config');
        if (r.ok) tdtKey = ((await r.json()).tianditu_key || '').trim();
      } catch (e) { /* 配置读取失败：只叠 ArcGIS */ }
      // 在线卫星图叠加（WGS-84 对齐）；无网络时静默降级到内置 NaturalEarthII
      try {
        viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          maximumLevel: 19, credit: 'Esri World Imagery',
        }));
        // 天地图影像盖在 ArcGIS 之上：偏远地区 ArcGIS 高层级只回「Map data not yet available」
        // 灰图（HTTP 200 占位图无法拦截），天地图 img_w 到 z18 仍是真实影像；
        // 更近时 Cesium 自动放大 z18 上级瓦片——变糊但不会变灰
        if (tdtKey) {
          viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
            url: 'https://t{s}.tianditu.gov.cn/DataServer?T=img_w&x={x}&y={y}&l={z}&tk=' + tdtKey,
            subdomains: ['0', '1', '2', '3', '4', '5', '6', '7'],
            tilingScheme: new Cesium.WebMercatorTilingScheme(),
            maximumLevel: 18, credit: '国家地理信息公共服务平台 天地图影像',
          }));
        }
      } catch (e) { /* 离线环境：保留 NaturalEarthII */ }
      // 天地图中文地名注记层（同主系统 TiandituProvider 的 cia_w 影像模式）
      try {
        if (tdtKey) {
          viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
            url: 'https://t{s}.tianditu.gov.cn/DataServer?T=cia_w&x={x}&y={y}&l={z}&tk=' + tdtKey,
            subdomains: ['0', '1', '2', '3', '4', '5', '6', '7'],
            tilingScheme: new Cesium.WebMercatorTilingScheme(),
            maximumLevel: 18, credit: '国家地理信息公共服务平台 天地图',
          }));
        }
      } catch (e) { /* 离线环境：无注记，底图照常 */ }
      viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#2a2f3a');
      $('#pv-viewer').classList.add('ready');
    } finally {
      engineLoading = false;
    }
  }

  async function loadTileset(dir) {
    await ensureEngine();
    curDir = dir.replace(/[\\/]+$/, '');
    const base = '/model/' + b64url(curDir) + '/';
    const res = await fetch(base + 'tileset.json');
    if (!res.ok) throw new Error('tileset.json 读取失败（HTTP ' + res.status + '）');
    const json = await res.json();
    const box = json && json.root && json.root.boundingVolume && json.root.boundingVolume.box;
    pivot = (Array.isArray(box) && box.length >= 3) ? [box[0], box[1], box[2]] : [0, 0, 0];
    if (tileset) { viewer.scene.primitives.remove(tileset); tileset = null; }
    tileset = await Cesium.Cesium3DTileset.fromUrl(base + 'tileset.json');
    viewer.scene.primitives.add(tileset);
    t = { x: 0, y: 0, z: 0, heading: 0, pitch: 0, roll: 0, sx: 1, sy: 1, sz: 1 };
    applyTransform();
    applyOpacity();  // tileset 重建，滑块当前值重应用到新对象
    createGizmo();
    viewer.scene.camera.flyToBoundingSphere(tileset.boundingSphere, { duration: 1.2 });
    $('#pv-refresh').disabled = false;
    $('#pv-save').disabled = false;
    return true;
  }

  async function openPreview() {
    const dir = $('#pv-src').value.trim();
    if (!dir) { pvStatus('请先填写产物目录', 'err'); return; }
    pvStatus('加载 3D 引擎与模型…（首次约几秒）', '');
    $('#pv-open').disabled = true;
    try {
      await loadTileset(dir);
      pvStatus('模型已加载。拖拽箭头平移 / 圆环旋转 / 轴上方块缩放 / 黄色方块斜移，悬停滚轮微调 0.01', 'ok');
    } catch (e) {
      pvStatus('加载失败：' + e.message, 'err');
    } finally {
      $('#pv-open').disabled = false;
    }
  }

  async function refreshPreview() {
    if (!curDir) return;
    if (!isZero(t) && !window.confirm('有未保存的调整，手动更新将丢弃这些调整，继续？')) return;
    try {
      await loadTileset(curDir);
      pvStatus('已从磁盘重新加载（未保存的调整已丢弃）', 'ok');
    } catch (e) {
      pvStatus('重新加载失败：' + e.message, 'err');
    }
  }

  async function saveBake() {
    if (!tileset || !curDir) return;
    if (isZero(t)) { pvStatus('当前没有调整，无需保存', 'err'); return; }
    pvStatus('保存中…（烘焙 root.transform）', '');
    $('#pv-save').disabled = true;
    try {
      const r = await fetch('/api/bake-transform', {
        method: 'POST',
        body: JSON.stringify({ dir: curDir, matrix: bakedMatrix() }),
      });
      const j = await r.json();
      if (!r.ok || j.error) throw new Error(j.error || 'HTTP ' + r.status);
      await loadTileset(curDir);  // 重新加载，让 root.transform 生效、参数归零
      pvStatus('已保存并烘焙进 tileset.json（原文件备份为 tileset.json.bak），可继续注册到系统', 'ok');
    } catch (e) {
      pvStatus('保存失败：' + e.message, 'err');
    } finally {
      $('#pv-save').disabled = false;
    }
  }

  function resetTransform() {
    t = { x: 0, y: 0, z: 0, heading: 0, pitch: 0, roll: 0, sx: 1, sy: 1, sz: 1 };
    applyTransform();
    pvStatus('变换已重置（未保存到磁盘）', '');
  }

  function bindInputs() {
    for (const k of ['x', 'y', 'z', 'heading', 'pitch', 'roll', 'sx', 'sy', 'sz']) {
      const el = $('#pv-' + k);
      if (!el) continue;
      el.addEventListener('input', () => {
        const v = parseFloat(el.value);
        if (!isNaN(v)) { t = { ...t, [k]: v }; applyTransform(); }
      });
    }
    const opEl = $('#pv-opacity');
    if (opEl) {
      opEl.addEventListener('input', () => {
        opacityPct = parseInt(opEl.value, 10);
        const val = $('#pv-opacity-val');
        if (val) val.textContent = opacityPct + '%';
        applyOpacity();
      });
    }
    const suEl = $('#pv-su');
    if (suEl) {
      suEl.addEventListener('input', () => {
        const v = parseFloat(suEl.value);
        if (!isNaN(v) && v > 0) {
          t = { ...t, sx: v, sy: v, sz: v };
          applyTransform();
        }
      });
    }
  }

  function bind() {
    $('#pv-open').addEventListener('click', openPreview);
    $('#pv-refresh').addEventListener('click', refreshPreview);
    $('#pv-save').addEventListener('click', saveBake);
    $('#pv-reset').addEventListener('click', resetTransform);
    const showEl = $('#pv-show');
    if (showEl) showEl.addEventListener('change', () => { if (gizmo) gizmo.setShow(showEl.checked); });
    bindInputs();
  }

  window.GeoPreview = {
    bind,
    show(outDir) {
      if (outDir && !$('#pv-src').value) $('#pv-src').value = outDir;
    },
    openPreview, refreshPreview, saveBake, resetTransform,
    viewer: () => viewer,
    state: () => ({ dir: curDir, t: { ...t }, hasTileset: !!tileset,
                    matrix: tileset ? Array.from(tileset.modelMatrix) : null,
                    baked: (tileset && !isZero(t)) ? bakedMatrix() : null }),
    debug: () => ({
      t: { ...t },
      axes: { x: axisColENU('x'), y: axisColENU('y'), z: axisColENU('z') },
      placement: (gizmo && gizmo.opts.getPlacement()) || null,
      opacity: opacityPct,
      styled: !!(tileset && tileset.style && tileset.style.color),
    }),
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
