#!/usr/bin/env python3
"""
Generate CGA-dithered demo images by running the actual cga-dither.effect
shader through a headless OpenGL context (moderngl + Mesa llvmpipe).

Run via Docker (handles all GL dependencies):
    ./tools/make_demo.sh

Or directly if moderngl is available locally:
    python3 tools/make_demo.py
"""

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import moderngl
except ImportError:
    sys.exit(
        "moderngl not found.\n"
        "Run this script through Docker:  ./tools/make_demo.sh\n"
        "Or install locally:              pip install moderngl"
    )

# ---------------------------------------------------------------------------
# OBS .effect → GLSL fragment shader transpiler
# ---------------------------------------------------------------------------

def _remove_braced_block(src: str, keyword: str) -> str:
    """Remove a top-level block starting with 'keyword ... { ... }'."""
    pos = src.find(keyword)
    if pos == -1:
        return src
    brace = src.find('{', pos)
    if brace == -1:
        return src
    depth, i = 0, brace
    while i < len(src):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[:pos] + src[i + 1:]
        i += 1
    return src


def effect_to_fragment_glsl(effect_path: Path) -> str:
    """
    Convert an OBS .effect file to a standalone GLSL 3.30 fragment shader.

    The transpiler handles only the constructs present in cga-dither.effect;
    it is not a general-purpose HLSL compiler.
    """
    src = effect_path.read_text()

    # --- Remove OBS boilerplate blocks ---
    src = re.sub(r'sampler_state\s+\w+\s*\{[^}]*\}', '', src, flags=re.DOTALL)
    src = _remove_braced_block(src, 'technique')
    src = re.sub(r'struct\s+VertData\s*\{[^}]*\}', '', src, flags=re.DOTALL)
    # Remove the vertex shader function (VertData return type is the tell)
    src = re.sub(
        r'VertData\s+\w+\s*\([^)]*\)\s*\{[^}]*\}', '', src, flags=re.DOTALL
    )

    # --- Uniform declarations ---
    src = re.sub(r'uniform\s+float4x4\s+ViewProj\s*;', '', src)
    src = re.sub(
        r'uniform\s+texture2d\s+\w+\s*;', 'uniform sampler2D image;', src
    )

    # --- HLSL type → GLSL type (longest first to avoid partial replacement) ---
    for hlsl, glsl in [
        ('float4x4', 'mat4'),
        ('float4',   'vec4'),
        ('float3',   'vec3'),
        ('float2',   'vec2'),
    ]:
        src = re.sub(r'\b' + hlsl + r'\b', glsl, src)

    # --- HLSL built-ins → GLSL ---
    src = re.sub(r'\bfmod\b', 'mod', src)

    # --- Texture sampling ---
    src = re.sub(r'\bimage\.Sample\(\w+,\s*', 'texture(image, ', src)

    # --- Semantic annotations (always ALLCAPS after a colon) ---
    src = re.sub(r'\s*:\s*[A-Z][A-Z0-9_]*', '', src)

    # --- Adapt PSCGADither to accept a plain vec2 instead of VertData ---
    src = re.sub(
        r'vec4\s+PSCGADither\s*\(\s*VertData\s+v_in\s*\)',
        'vec4 PSCGADither(vec2 v_uv)',
        src,
    )
    src = src.replace('v_in.uv', 'v_uv')

    header = (
        '#version 330 core\n'
        'in  vec2 v_uv;\n'
        'out vec4 fragColor;\n'
    )
    footer = '\nvoid main() { fragColor = PSCGADither(v_uv); }\n'

    return header + src + footer


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# Simple fullscreen-triangle vertex shader (no uniforms needed)
_VERTEX_SRC = """
#version 330 core
in  vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv        = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

# CGA palette data (mirrors cga-filter.c)
C0, C1, C2, C3 = 0.0, 85/255, 170/255, 1.0
PALETTES = {
    'pal1_hi': [(C0,C0,C0), (C1,C3,C3), (C3,C1,C3), (C3,C3,C3)],
    'pal1_lo': [(C0,C0,C0), (C0,C2,C2), (C2,C0,C2), (C2,C2,C2)],
    'pal0_hi': [(C0,C0,C0), (C1,C3,C1), (C3,C1,C1), (C3,C3,C1)],
    'pal0_lo': [(C0,C0,C0), (C0,C2,C0), (C2,C0,C0), (C2,C1,C0)],
}

_fullscreen_quad = np.array(
    [-1,-1,  1,-1,  -1,1,  1,1], dtype=np.float32
)


def render(
    ctx: 'moderngl.Context',
    prog: 'moderngl.Program',
    img: Image.Image,
    palette_name: str,
    pixel_size: int,
) -> Image.Image:
    img = img.convert('RGB')
    w, h = img.size

    # Upload source texture (flip vertically: OpenGL origin is bottom-left)
    flipped = np.asarray(img.transpose(Image.FLIP_TOP_BOTTOM), dtype=np.uint8)
    tex = ctx.texture((w, h), 3, flipped.tobytes())
    tex.filter = moderngl.NEAREST, moderngl.NEAREST
    tex.use(0)

    prog['image']      = 0
    prog['resolution'] = (float(w), float(h))
    prog['pixel_size'] = float(pixel_size)
    for i, color in enumerate(PALETTES[palette_name]):
        prog[f'pal{i}'] = color

    fbo = ctx.framebuffer(color_attachments=[ctx.texture((w, h), 4)])
    fbo.use()
    fbo.clear()

    vbo = ctx.buffer(_fullscreen_quad.tobytes())
    vao = ctx.simple_vertex_array(prog, vbo, 'in_pos')
    vao.render(moderngl.TRIANGLE_STRIP)

    # Read back and flip to top-left origin
    data   = fbo.read(components=3)
    result = Image.frombytes('RGB', (w, h), data).transpose(Image.FLIP_TOP_BOTTOM)

    tex.release(); fbo.release(); vbo.release(); vao.release()
    return result


# ---------------------------------------------------------------------------
# Demo configuration
# ---------------------------------------------------------------------------

VARIANTS = [
    # (palette_name,  pixel_size,  output_suffix)
    ('pal1_hi', 1, 'pal1hi_px1'),
    ('pal0_hi', 1, 'pal0hi_px1'),
    ('pal1_hi', 4, 'pal1hi_px4'),
    ('pal0_hi', 4, 'pal0hi_px4'),
]

SOURCES = [
    ('lab_original.jpg',     'lab'),
    ('medical_original.jpg', 'medical'),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    project_root = Path(__file__).resolve().parent.parent
    effect_path  = project_root / 'data' / 'shaders' / 'cga-dither.effect'
    demo_dir     = project_root / 'demo'

    print(f'Transpiling {effect_path.name} ...')
    fragment_src = effect_to_fragment_glsl(effect_path)

    print('Creating OpenGL context (Mesa software renderer) ...')
    ctx  = moderngl.create_standalone_context(backend='egl')
    prog = ctx.program(vertex_shader=_VERTEX_SRC, fragment_shader=fragment_src)

    for filename, name in SOURCES:
        src = demo_dir / filename
        if not src.exists():
            print(f'SKIP {filename} — not found in demo/', file=sys.stderr)
            continue

        print(f'\n{filename}  →  {name}')
        img = Image.open(src)

        for pal, px, suffix in VARIANTS:
            out_path = demo_dir / f'{name}_{suffix}.png'
            print(f'  {out_path.name} ...', end=' ', flush=True)
            result = render(ctx, prog, img, pal, px)
            result.save(out_path)
            print('done')

    ctx.release()
    print('\nAll done.')


if __name__ == '__main__':
    main()
