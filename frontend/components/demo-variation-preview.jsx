"use client";

// Show the prediction for the selected inputs without sampling alternatives.
export function DemoVariationPreview({ preview, onPointerDown }) {
  return (
    <div className="demo-variation-preview">
      <div className="demo-image-button">
        <img className="demo-flame-image" draggable={false}
          style={{ touchAction: "none" }} onPointerDown={onPointerDown}
          src={preview.hybrid} alt="Hybrid CNN flame estimate" width="256" height="256" />
      </div>
      <p className="demo-frame-conditions">{preview.conditions}</p>
    </div>
  );
}
