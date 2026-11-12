import * as maplibregl from 'maplibre-gl';

// Schematic 3D footprint-to-mount surfaces. Actual zone visibility is supplied
// by the solver, never inferred from these display meshes or the basemap.
export function frustumLayer(cameras, center) {
  const origin = maplibregl.MercatorCoordinate.fromLngLat(center);
  const triangles = [], lines = [];
  function point(lon, lat, height) {
    const p = maplibregl.MercatorCoordinate.fromLngLat([lon, lat], height);
    return [p.x - origin.x, p.y - origin.y, p.z];
  }
  function vertex(target, p, rgb, alpha) { target.push(...p, ...rgb, alpha); }
  for (const c of cameras) {
    const rgb = [1,3,5].map(i => parseInt(c.color.slice(i, i + 2), 16) / 255);
    const apex = point(c.lon, c.lat, c.height_m);
    const edge = c.fov_polygon.filter(p => Math.abs(p[0] - c.lon) + Math.abs(p[1] - c.lat) > 1e-10);
    for (let i = 0; i < edge.length - 1; i++) {
      for (const p of [apex, point(...edge[i], 0.3), point(...edge[i+1], 0.3)]) vertex(triangles, p, rgb, 0.12);
    }
    for (const end of [edge[0], edge.at(-1)]) if (end) {
      vertex(lines, apex, rgb, 0.85); vertex(lines, point(...end, 0.3), rgb, 0.85);
    }
    vertex(lines, point(c.lon, c.lat, 0), rgb, 1); vertex(lines, apex, rgb, 1);
    // Center ray uses actual azimuth and downward tilt. Ends at the ground if necessary.
    const tilt = c.tilt_deg * Math.PI / 180, az = c.azimuth_deg * Math.PI / 180;
    const distance = tilt > 0 ? Math.min(c.range_m, c.height_m / Math.tan(tilt)) : c.range_m;
    const end = [c.lon + Math.sin(az) * distance / (111320 * Math.cos(c.lat * Math.PI / 180)), c.lat + Math.cos(az) * distance / 111320];
    vertex(lines, apex, rgb, 1); vertex(lines, point(...end, Math.max(0.3, c.height_m - distance * Math.tan(tilt))), rgb, 1);
  }
  let program, buffer, position, color, matrix, vao;
  return {
    id: 'camera-frustums', type: 'custom', renderingMode: '3d',
    onAdd(_map, gl) {
      function shader(type, source) {
        const s = gl.createShader(type); gl.shaderSource(s, source); gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
        return s;
      }
      const vs = shader(gl.VERTEX_SHADER, 'attribute vec3 a_pos; attribute vec4 a_color; uniform mat4 u_matrix; varying vec4 v_color; void main(){gl_Position=u_matrix*vec4(a_pos,1.0); v_color=a_color;}');
      const fs = shader(gl.FRAGMENT_SHADER, 'precision mediump float; varying vec4 v_color; void main(){gl_FragColor=v_color;}');
      program = gl.createProgram(); gl.attachShader(program, vs); gl.attachShader(program, fs); gl.linkProgram(program);
      gl.deleteShader(vs); gl.deleteShader(fs);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
      buffer = gl.createBuffer(); vao = gl.createVertexArray();
      position = gl.getAttribLocation(program, 'a_pos'); color = gl.getAttribLocation(program, 'a_color'); matrix = gl.getUniformLocation(program, 'u_matrix');
      gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([...triangles, ...lines]), gl.STATIC_DRAW);
      gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 3, gl.FLOAT, false, 28, 0);
      gl.enableVertexAttribArray(color); gl.vertexAttribPointer(color, 4, gl.FLOAT, false, 28, 12);
      gl.bindVertexArray(null);
    },
    render(gl, input) {
      const m = input.defaultProjectionData.mainMatrix;
      const translated = new Float32Array(m);
      for (let i = 0; i < 4; i++) translated[12+i] = m[i] * origin.x + m[4+i] * origin.y + m[12+i];
      gl.useProgram(program); gl.uniformMatrix4fv(matrix, false, translated); gl.bindVertexArray(vao);
      gl.enable(gl.DEPTH_TEST); gl.depthMask(false); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.disable(gl.CULL_FACE);
      gl.drawArrays(gl.TRIANGLES, 0, triangles.length / 7);
      gl.drawArrays(gl.LINES, triangles.length / 7, lines.length / 7);
      gl.depthMask(true); gl.bindVertexArray(null);
    },
    onRemove(_map, gl) { gl.deleteBuffer(buffer); gl.deleteVertexArray(vao); gl.deleteProgram(program); },
  };
}
