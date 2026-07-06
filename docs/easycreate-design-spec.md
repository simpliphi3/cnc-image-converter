# EasyCreate (easycreate.vectric.com) — Design Specification
## For: cnc-image-converter Project Enhancement

> Research conducted via live browser automation session.
> Focus: Image-to-CNC pipeline, STL export accuracy, inversion fix.

---

## 1. Overview

EasyCreate is a web-based tool by Vectric that converts images (and AI-generated content) into 3D relief models suitable for CNC machining. It outputs V3M (Vectric proprietary), TIFF (16-bit heightmap), and STL files.

**Primary pipeline (relevant to cnc-image-converter):**
1. Upload an image → pre-process to grayscale heightmap
2. Optionally enhance (AI sharpening/clarity)
3. Configure background removal and crop
4. Process into a 3D model (internally stored as a Float32Array heightmap)
5. Adjust height parameters interactively in a THREE.js preview
6. Export as STL, TIFF, or V3M

---

## 2. User Workflow (5-Step URL Pattern)

| Step | URL Pattern | Description |
|------|-------------|-------------|
| 1 | `/` | Home — upload or AI-generate |
| 2 | `/create?method=upload` | Upload image via drag-and-drop |
| 3 | `/{jobId}/create/enhance` | Optional AI enhancement |
| 4 | `/{jobId}/create/edit` | Remove background, crop |
| 5 | `/{jobId}/processing` → `/{jobId}/preview` | Process model, then interactive preview + export |

**Job ID format:** ULID (e.g., `01KWM68BG3CMVZ79N9V1P70HGY`)

---

## 3. Internal Data Model

### Heightmap Storage
```
tiffData: {
  data: Float32Array,   // normalized pixel values: 0.0 (black/deep) to 1.0 (white/tall)
  width: number,        // image width in pixels
  height: number,       // image height in pixels
  min: 0,               // always 0.0 after normalization
  max: 1                // always 1.0 after normalization
}
```

### Available TIFF Files (per job)
- `/{jobId}/detail_map.tiff` — AI-enhanced heightmap (used when enhancements are applied)
- `/{jobId}/corrected_16bit.tiff` — Base 16-bit grayscale heightmap (used when skipping enhancement)

### 3D Viewer
- Engine: **THREE.js r180** (`window.__THREE__ = 180`)
- Renders a mesh from the heightmap with real-time parameter updates
- Camera: perspective, orbital controls
- Lighting: standard ambient + directional

---

## 4. Preview Page — All Controls

### 4.1 Z-Scale (Height) Slider
| Property | Value |
|----------|-------|
| Label | "Z Scale" |
| Min | 0 |
| Max | 200 |
| Step | 1 |
| Default | 100 |
| Unit | implied mm (or relative units) |
| Effect | Multiplies all heightmap values: `z = pixelValue * zScale` |

### 4.2 Detail Slider
| Property | Value |
|----------|-------|
| Label | "Detail" |
| Min | 0 |
| Max | 100 |
| Step | 1 |
| Default | 25 |
| Effect | Controls blend between flat (`corrected_16bit.tiff`) and detail-enhanced (`detail_map.tiff`) heightmaps |

**Blend formula:**
```
finalPixel = (detailMap * detail/100) + (flatMap * (1 - detail/100))
```

### 4.3 Replace Below (Threshold) Slider
| Property | Value |
|----------|-------|
| Label | "Replace Below" |
| Min | 0 |
| Max | 100 |
| Step | 1 |
| Default | 0 |
| Unit | % of heightmap value |
| Effect | Pixels with heightmap value below this threshold are set to 0 (flat base). Used for background removal/cleanup. |

### 4.4 Edit Height Curve (Collapsible Section)
A spline curve editor that remaps input heightmap values to output height values.

**Curve data format:**
```json
curvePoints: [
  { "x": 0, "y": 0 },
  { "x": 1, "y": 1 }
]
```
- X axis: input pixel value (0.0–1.0)
- Y axis: output height value (0.0–1.0, before zScale multiplication)
- Default: linear (identity) curve

**Curve Presets (dropdown):**
| Preset | Description |
|--------|-------------|
| Linear | Identity — no remapping (default) |
| Gentle | Slight S-curve, softens transitions |
| Medium | Moderate S-curve |
| Aggressive | Strong S-curve, high contrast |
| Custom | User-drawn freehand curve |

**Curve Editor Interactions:**
- Click canvas: add control point
- Drag point: move control point
- Right-click point: remove control point

### 4.5 Scale Heights Along Y-Axis (Collapsible Section)
A per-row height scaling curve. Allows tapering or emphasizing heights at different Y positions.

**Data format:**
```json
yAxisScalePoints: [
  { "x": 0, "y": 1.0 },
  { "x": 1, "y": 1.0 }
]
```
- Default: flat (1.0 everywhere = no scaling)

**Presets:**
| Preset | Description |
|--------|-------------|
| Flat | No Y-axis scaling (default) |
| Taper Top | Heights reduce toward top of image |
| Taper Bottom | Heights reduce toward bottom of image |
| Emphasize Middle | Heights amplified in center Y rows |
| Reduce Middle | Heights reduced in center Y rows |

### 4.6 Scale Heights Along X-Axis (Collapsible Section)
Same as Y-axis scaling but applied per-column.

**Data format:**
```json
xAxisScalePoints: [
  { "x": 0, "y": 1.0 },
  { "x": 1, "y": 1.0 }
]
```
- Default: flat (1.0 everywhere = no scaling)

**Presets:** Same set as Y-axis (Flat, Taper Top, Taper Bottom, Emphasize Middle, Reduce Middle)

---

## 5. Processing Pipeline (Transformation Order)

When generating the final mesh, transformations are applied in this order:

```
1. Load Float32Array heightmap (0.0–1.0 normalized)
2. Blend detail map: pixel = (detailMap * detail%) + (flatMap * (1 - detail%))
3. Apply "Replace Below" threshold: if pixel < threshold, pixel = 0
4. Apply Height Curve remap: pixel = curveRemap(pixel)
5. Apply Y-axis scale: pixel *= yAxisScale(rowPosition)
6. Apply X-axis scale: pixel *= xAxisScale(colPosition)
7. Apply Z-Scale: z = pixel * zScale
8. Construct mesh vertices at (x, y, z)
```

---

## 6. Export Formats

All three exports are triggered by `ne(format)` function calls:

| Format | Function Call | Description | Credit Required |
|--------|--------------|-------------|-----------------|
| V3M | `ne("v3m")` | Vectric proprietary format, opens in Aspire/VCarve | Standard |
| TIFF | `ne("tiff")` | 16-bit grayscale heightmap | Standard |
| STL | `ne("stl")` | Binary STL mesh | Additional purchase required |

**STL Credit Flag (found in component state):**
```json
stlExportPurchased: false
```
STL export requires a separate purchase/upgrade beyond base credits.

---

## 7. STL Export — Technical Specification

### 7.1 Correct Vertex Generation
```python
for row in range(height):
    for col in range(width):
        pixel = heightmap[row * width + col]   # Float32, 0.0–1.0
        x = col * xSpacing
        y = row * ySpacing
        z = pixel * zScale                      # CORRECT: white = tall
        vertices[row][col] = (x, y, z)
```

### 7.2 Face/Triangle Winding Order (normals pointing UP/+Z)
```
For each quad formed by 4 adjacent vertices:
  TL = vertices[row][col]
  TR = vertices[row][col+1]
  BL = vertices[row+1][col]
  BR = vertices[row+1][col+1]

  Triangle 1 (counter-clockwise from above = normal points +Z):
    v0=TL, v1=BL, v2=TR

  Triangle 2:
    v0=TR, v1=BL, v2=BR
```

### 7.3 Watertight Mesh (Base Plate)
For a printable/machinable STL, add closing faces:
- 4 side walls (connecting top surface edges to z=0 plane)
- 1 bottom face (flat rectangle at z=0)

### 7.4 Binary STL Format
```
Header: 80 bytes (arbitrary text)
Triangle count: uint32 (4 bytes)
Per triangle (50 bytes each):
  Normal vector: 3x float32 (12 bytes)
  Vertex 1: 3x float32 (12 bytes)
  Vertex 2: 3x float32 (12 bytes)
  Vertex 3: 3x float32 (12 bytes)
  Attribute byte count: uint16 = 0 (2 bytes)
```

---

## 8. Root Cause: STL Inversion Bug

### The Problem
If the existing `cnc-image-converter` STL output is inverted (raised areas appear as depressions), the likely cause is one of:

**Cause A — Z-value negation:**
```python
# WRONG (inverted):
z = maxZ - (pixelValue * zScale)
z = zScale - (pixelValue * zScale)
z = (1.0 - pixelValue) * zScale

# CORRECT:
z = pixelValue * zScale
```

**Cause B — Image read direction (Y-axis flip):**
```python
# WRONG: reading rows bottom-to-top but treating as top-to-bottom
# CORRECT: be consistent — row 0 = top of image, iterate forward
```

**Cause C — Face winding order (normals pointing DOWN instead of UP):**
```python
# WRONG: clockwise winding from above
v0=TL, v1=TR, v2=BL   # normals point -Z (downward)

# CORRECT: counter-clockwise from above
v0=TL, v1=BL, v2=TR   # normals point +Z (upward)
```

**Cause D — Pixel value interpretation:**
```python
# WRONG: treating black (0) as tall, white (255) as flat
z = (255 - pixelValue) / 255.0 * zScale

# CORRECT: white = tall, black = flat
z = pixelValue / 255.0 * zScale
```

### Recommended Fix Checklist
- [ ] Confirm `z = pixelValue * zScale` (not subtracted from max)
- [ ] Confirm white pixel (255 or 1.0) produces the HIGHEST z value
- [ ] Confirm face winding produces normals pointing +Z (up)
- [ ] Confirm Y-axis iteration is consistent (don't flip)
- [ ] Test with a gradient image: should produce a ramp, not an inverted ramp

---

## 9. Enhancement Step — Detail

### AI Enhancement Options (Step 3)
When not skipped, three preset options are offered:
| Option | Description |
|--------|-------------|
| Sharpen Details | Increases edge definition |
| Improve Clarity | Smooths and clarifies the heightmap |
| Add Definition | Adds surface definition/texture |

**Custom Enhance:** Toggle reveals a text prompt field for custom AI enhancement instructions.

**Skip Option:** "Skip enhancement" button bypasses all AI processing and uses raw uploaded image.

---

## 10. Edit Step — Background & Crop (Step 4)

### Remove Background
- Toggle: on/off
- When ON: AI segments and removes background pixels (sets to 0 in heightmap)
- Uses AI segmentation (Vectric cloud processing)

### Crop
- Standard rectangular crop tool
- Applied before model generation

### Create Model Button
- Triggers cloud processing job
- **Costs 4 credits** per model generation
- Shows "Brewing a topographical potion..." loading state (~10 seconds for 200×200 image)

---

## 11. Gap Analysis: cnc-image-converter vs EasyCreate

| Feature | EasyCreate | cnc-image-converter Status |
|---------|-----------|---------------------------|
| Z-Scale slider | 0–200, default 100 | ⚠️ Verify implementation |
| Detail blend (2 maps) | detail_map + flat blend | ❓ Likely not implemented |
| Replace Below threshold | 0–100%, clips to 0 | ❓ Check if implemented |
| Height Curve (spline remap) | Full curve editor | ❓ Likely not implemented |
| Y-axis height scaling | Per-row scale curve | ❓ Likely not implemented |
| X-axis height scaling | Per-column scale curve | ❓ Likely not implemented |
| STL watertight base | Sides + bottom face | ⚠️ Verify completeness |
| Correct Z direction | white=tall, z=pixel*scale | 🔴 LIKELY BUG — verify |
| Face winding (normals up) | Counter-clockwise from +Z | 🔴 LIKELY BUG — verify |
| TIFF export (16-bit) | 16-bit grayscale | ❓ Check bit depth |
| Background removal | AI segmentation | ❌ Out of scope (cloud AI) |

---

## 12. Python Pseudocode — Correct STL Generation

```python
import struct
import numpy as np
from PIL import Image

def image_to_stl(image_path, output_path, z_scale=10.0, x_spacing=1.0, y_spacing=1.0):
    """
    Convert a grayscale heightmap image to a watertight binary STL.
    
    Convention (matching EasyCreate):
    - White (255) = tallest point
    - Black (0) = base level (z=0)
    - z = (pixel/255) * z_scale
    """
    # Load and normalize
    img = Image.open(image_path).convert('L')
    pixels = np.array(img, dtype=np.float32) / 255.0  # 0.0 to 1.0
    height, width = pixels.shape
    
    # Apply transformations (in order matching EasyCreate pipeline):
    # 1. Replace Below threshold (optional)
    # pixels[pixels < threshold] = 0.0
    
    # 2. Height Curve remap (optional spline)
    # pixels = apply_curve(pixels, curve_points)
    
    # 3. Y-axis scaling (optional)
    # for row in range(height):
    #     pixels[row, :] *= y_scale_at(row / height)
    
    # 4. X-axis scaling (optional)
    # for col in range(width):
    #     pixels[:, col] *= x_scale_at(col / width)
    
    # 5. Z-Scale
    z_values = pixels * z_scale   # CRITICAL: white = tall
    
    # Build vertex grid
    # Row 0 = top of image, row (height-1) = bottom
    verts = np.zeros((height, width, 3), dtype=np.float32)
    for row in range(height):
        for col in range(width):
            verts[row][col] = [
                col * x_spacing,
                row * y_spacing,
                z_values[row][col]
            ]
    
    triangles = []
    
    # Top surface triangles
    for row in range(height - 1):
        for col in range(width - 1):
            TL = verts[row][col]
            TR = verts[row][col + 1]
            BL = verts[row + 1][col]
            BR = verts[row + 1][col + 1]
            
            # Counter-clockwise from above = normal points +Z (UP)
            triangles.append((TL, BL, TR))  # Triangle 1
            triangles.append((TR, BL, BR))  # Triangle 2
    
    # Base plate (z=0)
    BL_base = [0, 0, 0]
    BR_base = [(width-1)*x_spacing, 0, 0]
    TL_base = [0, (height-1)*y_spacing, 0]
    TR_base = [(width-1)*x_spacing, (height-1)*y_spacing, 0]
    
    # Bottom face (normal points -Z / downward)
    triangles.append((BL_base, BR_base, TL_base))
    triangles.append((TR_base, TL_base, BR_base))
    
    # Side walls (4 sides)
    # Front (row=0), Back (row=height-1), Left (col=0), Right (col=width-1)
    for col in range(width - 1):
        # Front wall (row 0)
        v0 = verts[0][col];   v1 = verts[0][col+1]
        b0 = [v0[0], v0[1], 0]; b1 = [v1[0], v1[1], 0]
        triangles.append((v0, b0, v1))
        triangles.append((v1, b0, b1))
        # Back wall (last row)
        v0 = verts[-1][col];  v1 = verts[-1][col+1]
        b0 = [v0[0], v0[1], 0]; b1 = [v1[0], v1[1], 0]
        triangles.append((v1, b0, v0))
        triangles.append((b1, b0, v1))
    
    for row in range(height - 1):
        # Left wall (col 0)
        v0 = verts[row][0];   v1 = verts[row+1][0]
        b0 = [v0[0], v0[1], 0]; b1 = [v1[0], v1[1], 0]
        triangles.append((v1, b0, v0))
        triangles.append((b1, b0, v1))
        # Right wall (last col)
        v0 = verts[row][-1];  v1 = verts[row+1][-1]
        b0 = [v0[0], v0[1], 0]; b1 = [v1[0], v1[1], 0]
        triangles.append((v0, b0, v1))
        triangles.append((v1, b0, b1))
    
    # Write binary STL
    def calc_normal(v0, v1, v2):
        a = np.array(v1) - np.array(v0)
        b = np.array(v2) - np.array(v0)
        n = np.cross(a, b)
        length = np.linalg.norm(n)
        return (n / length).tolist() if length > 0 else [0, 0, 1]
    
    with open(output_path, 'wb') as f:
        f.write(b'EasyCreate-compatible STL output' + b' ' * 48)  # 80-byte header
        f.write(struct.pack('<I', len(triangles)))
        for tri in triangles:
            v0, v1, v2 = [np.array(v, dtype=np.float32) for v in tri]
            normal = calc_normal(v0, v1, v2)
            f.write(struct.pack('<fff', *normal))
            f.write(struct.pack('<fff', *v0))
            f.write(struct.pack('<fff', *v1))
            f.write(struct.pack('<fff', *v2))
            f.write(struct.pack('<H', 0))  # attribute byte count
    
    print(f"Written {len(triangles)} triangles to {output_path}")
```

---

## 13. Credits System

- **Base credits:** Given on account creation (observed: 79 credits starting balance)
- **Create Model:** Costs **4 credits** per generation
- **STL Export:** Requires a **separate purchase** (`stlExportPurchased: false` by default)
- **V3M and TIFF exports:** Included with standard credits

---

## 14. Additional Notes

### File Naming Convention
- Job files stored at: `/{jobId}/filename.ext`
- Example: `/01KWM68BG3CMVZ79N9V1P70HGY/detail_map.tiff`

### Analytics & Error Tracking
- Sentry for error reporting
- Google Analytics
- PostHog for product analytics

### Supported Input Formats
Based on upload UI: standard image formats (PNG, JPG implied), plus the AI generation path (text prompt → image)

### Tutorial Topics (from /support page)
- Getting Started with EasyCreate
- How to upload an image
- How to use AI enhancement
- Adjusting height and detail
- Exporting to Vectric software
- Using STL files for CNC machining

---

*Spec generated via automated browser research session — July 3, 2026*
*Domain: easycreate.vectric.com*
*Researcher: Claude Sonnet (Anthropic)*
