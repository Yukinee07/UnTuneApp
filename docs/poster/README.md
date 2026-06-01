# Poster assets

Vector graphics for the FYP poster. Both files are standalone SVGs —
open them directly in any browser to preview.

## Files

| File | What it shows | Goes in poster box |
|------|---------------|--------------------|
| `block-diagram.svg` | System architecture: every component from input apps → VB-Cable → reader thread → HSTasNetVocals v12 internals (encoders, 5 LSTM blocks, mask heads, decoders, sum) → post-processing → writer → speakers | **BLOCK DIAGRAM** |
| `flowchart.svg` | Runtime flow as 3 parallel thread lanes (reader / main-GPU / writer) joined by `in_q` and `out_q`. Includes decision diamonds for queue-full / queue-empty / WASAPI-error and the reconnect loop | **FLOW CHART** |

## Importing into the poster

### If the poster template is Word (.docx) or PowerPoint (.pptx)

Word/PowerPoint do support SVG natively in modern versions (Office 365 / 2019+):

  Insert → Picture → This Device → pick the .svg

If your version is older, convert to PNG first (300+ DPI for print):

  1. Open the .svg in a browser
  2. Right-click → "Save image as…" → PNG  (Chrome/Edge do this directly)
  3. OR for higher quality: open in Inkscape → File → Export → PNG @ 300 DPI

### If the poster is built in a design tool (Figma, Illustrator, Canva)

Drag the .svg straight into the canvas. All shapes / arrows / text remain editable.

## Editing

The SVGs are hand-written, well-commented XML — open in any text editor
and the structure maps 1-to-1 onto the visible diagram. To change a
label or move a box, just edit the text/coordinates.

If you want recoloured versions (e.g. monochrome for B&W printing), the
colours are all referenced in the top section of each file and can be
search-replaced.
