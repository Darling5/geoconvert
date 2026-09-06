// geoconvert 坐标转换 3D 地球预览：大头针标点 WGS-84 结果位置。
// 引擎与影像层复用 preview.js 的 window.GeoCesium（ArcGIS 卫星图 + 天地图 + 灰图检测）。
(function () {
  'use strict';
  let viewer = null, pin = null, loading = false;
  const $ = (s) => document.querySelector(s);

  function status(t, cls) {
    const el = $('#cc-g-status');
    if (!el) return;
    el.textContent = t || '';
    el.className = cls || '';
  }

  async function ensure() {
    if (viewer) return viewer;
    if (!window.GeoCesium) return null;
    if (loading) return null;
    loading = true;
    status('正在加载 3D 引擎…', '');
    try {
      await window.GeoCesium.ensureCesium();
      const credit = document.createElement('div');
      credit.style.display = 'none';
      document.body.appendChild(credit);
      viewer = new Cesium.Viewer($('#cc-viewer'), {
        animation: false, timeline: false, baseLayerPicker: false, geocoder: false,
        homeButton: false, sceneModePicker: false, navigationHelpButton: false,
        fullscreenButton: false, infoBox: false, selectionIndicator: false,
        baseLayer: Cesium.ImageryLayer.fromProviderAsync(
          Cesium.TileMapServiceImageryProvider.fromUrl(
            Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII'))),
        creditContainer: credit,
      });
      await window.GeoCesium.addImagery(viewer);
      viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#2a2f3a');
      $('#cc-viewer').classList.add('ready');
      status('', '');
    } catch (e) {
      viewer = null;
      status('3D 引擎加载失败：' + e.message, 'err');
    } finally {
      loading = false;
    }
    return viewer;
  }

  async function mark(lon, lat, addr) {
    const v = await ensure();
    if (!v) return;
    if (pin) v.entities.remove(pin);
    const coords = lon.toFixed(6) + ', ' + lat.toFixed(6);
    const text = (addr && addr !== coords) ? addr + '\n' + coords : coords;
    pin = v.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat),
      billboard: {
        image: new Cesium.PinBuilder()
          .fromText('定', Cesium.Color.fromCssColorString('#3b9eff'), 46).toDataURL(),
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: text,
        font: '600 12.5px Consolas, "Microsoft YaHei", monospace',
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        showBackground: true,
        backgroundColor: Cesium.Color.fromCssColorString('#0a1626dd'),
        backgroundPadding: new Cesium.Cartesian2(7, 4),
        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
        pixelOffset: new Cesium.Cartesian2(0, -58),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    v.scene.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat, 5200),
      duration: 1.4,
    });
  }

  function clearPin() {
    if (viewer && pin) { viewer.entities.remove(pin); pin = null; }
  }

  window.CCGlobe = { ensure, mark, clearPin };
})();
