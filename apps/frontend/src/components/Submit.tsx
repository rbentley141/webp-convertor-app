import { useState, useRef, useEffect, type ChangeEvent, type FormEvent } from 'react'
import type { Job, AnyDict } from '../App'

type ImageType = "default" | "complex" | "graphic" | "product";
type SizeType = "banner" | "content" | "thumbnail" | "icon" | "other";
type CropMode = "manual" | "aspect-ratio";

type JobFormValues = {
  batch_id: number;
  image_id: number;
  lossless: boolean;
  text_focus: boolean;
  has_text: boolean;
  type: ImageType;
  crop_size_w: number;
  crop_size_h: number;
  crop_top_x: number;
  crop_top_y: number;
  crop_w: number;
  crop_h: number;
  size_type: SizeType;
  width: number | null;
  height: number | null;
}

type SubmitProps = {
  onSubmit: (dict: AnyDict, lastJob: boolean) => void | Promise<void>;
  batch_id: number;
  jobs: Job[];
}

function getImageDimensionsFromUrl(url: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      resolve({
        width: img.naturalWidth,
        height: img.naturalHeight,
      });
    };
    img.onerror = reject;
    img.src = url;
  });
}

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b);
}

function simplifyRatio(w: number, h: number): { ratioW: number; ratioH: number } {
  if (w <= 0 || h <= 0) return { ratioW: 1, ratioH: 1 };
  const divisor = gcd(Math.round(w), Math.round(h));
  return {
    ratioW: Math.round(w) / divisor,
    ratioH: Math.round(h) / divisor,
  };
}

export default function Submit({ onSubmit, batch_id, jobs }: SubmitProps) {
  const [idx, setIdx] = useState<number>(0);
  const [formValues, setFormValues] = useState<JobFormValues | null>(null);
  const [cropEnabled, setCropEnabled] = useState<boolean>(false);
  const [cropMode, setCropMode] = useState<CropMode>("manual");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Aspect ratio state
  const [aspectRatioW, setAspectRatioW] = useState<number>(16);
  const [aspectRatioH, setAspectRatioH] = useState<number>(9);
  const [aspectLockDimension, setAspectLockDimension] = useState<"width" | "height">("width");
  const [aspectInputValue, setAspectInputValue] = useState<number>(800);

  // Display dimensions
  const [displayWidth, setDisplayWidth] = useState<number>(0);
  const [displayHeight, setDisplayHeight] = useState<number>(0);
  const [naturalWidth, setNaturalWidth] = useState<number>(0);
  const [naturalHeight, setNaturalHeight] = useState<number>(0);

  // Drag-to-crop state
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  const MAX_DISPLAY_WIDTH = 600;
  const MAX_DISPLAY_HEIGHT = 500;

  useEffect(() => {
    if (idx >= jobs.length) return;

    const loadImage = async () => {
      const job = jobs[idx];
      try {
        const { width, height } = await getImageDimensionsFromUrl(job.url);

        setNaturalWidth(width);
        setNaturalHeight(height);

        const aspectRatio = width / height;
        let dispW = width;
        let dispH = height;

        if (dispW > MAX_DISPLAY_WIDTH) {
          dispW = MAX_DISPLAY_WIDTH;
          dispH = dispW / aspectRatio;
        }
        if (dispH > MAX_DISPLAY_HEIGHT) {
          dispH = MAX_DISPLAY_HEIGHT;
          dispW = dispH * aspectRatio;
        }

        setDisplayWidth(Math.round(dispW));
        setDisplayHeight(Math.round(dispH));

        setFormValues({
          batch_id: batch_id,
          image_id: job.id,
          lossless: false,
          text_focus: false,
          has_text: false,
          type: "default",
          crop_size_w: width,
          crop_size_h: height,
          crop_top_x: 0,
          crop_top_y: 0,
          crop_w: width,
          crop_h: height,
          size_type: "content",
          width: null,
          height: null,
        });

        setCropEnabled(false);
        setCropMode("manual");
      } catch (err) {
        console.error('Failed to load image dimensions:', err);
      }
    };

    loadImage();
  }, [idx, jobs, batch_id]);

  // Update crop dimensions when aspect ratio inputs change
  useEffect(() => {
    if (!cropEnabled || cropMode !== "aspect-ratio" || !formValues) return;
    if (aspectRatioW <= 0 || aspectRatioH <= 0 || aspectInputValue <= 0) return;

    const ratio = aspectRatioW / aspectRatioH;
    let newW: number;
    let newH: number;

    if (aspectLockDimension === "width") {
      newW = aspectInputValue;
      newH = Math.round(newW / ratio);
    } else {
      newH = aspectInputValue;
      newW = Math.round(newH * ratio);
    }

    // Clamp to image bounds
    newW = Math.min(newW, naturalWidth - formValues.crop_top_x);
    newH = Math.min(newH, naturalHeight - formValues.crop_top_y);

    if (newW > 0 && newH > 0) {
      setFormValues(prev => prev ? {
        ...prev,
        crop_w: newW,
        crop_h: newH,
      } : null);
    }
  }, [aspectRatioW, aspectRatioH, aspectLockDimension, aspectInputValue, cropEnabled, cropMode, naturalWidth, naturalHeight]);

  function displayToNatural(displayX: number, displayY: number): { x: number; y: number } {
    const scaleX = naturalWidth / displayWidth;
    const scaleY = naturalHeight / displayHeight;
    return {
      x: Math.round(Math.max(0, Math.min(displayX * scaleX, naturalWidth))),
      y: Math.round(Math.max(0, Math.min(displayY * scaleY, naturalHeight))),
    };
  }

  function naturalToDisplay(natX: number, natY: number): { x: number; y: number } {
    const scaleX = displayWidth / naturalWidth;
    const scaleY = displayHeight / naturalHeight;
    return {
      x: Math.round(natX * scaleX),
      y: Math.round(natY * scaleY),
    };
  }

  function handleMouseDown(e: React.MouseEvent<HTMLDivElement>) {
    if (!cropEnabled || !containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, displayWidth));
    const y = Math.max(0, Math.min(e.clientY - rect.top, displayHeight));

    setIsDragging(true);
    setDragStart({ x, y });

    const natural = displayToNatural(x, y);
    setFormValues(prev => prev ? {
      ...prev,
      crop_top_x: natural.x,
      crop_top_y: natural.y,
      crop_w: 0,
      crop_h: 0,
    } : null);
  }

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!isDragging || !dragStart || !containerRef.current || !formValues) return;

    const rect = containerRef.current.getBoundingClientRect();
    const currentX = Math.max(0, Math.min(e.clientX - rect.left, displayWidth));
    const currentY = Math.max(0, Math.min(e.clientY - rect.top, displayHeight));

    const startNat = displayToNatural(dragStart.x, dragStart.y);
    const currentNat = displayToNatural(currentX, currentY);

    let minX = Math.min(startNat.x, currentNat.x);
    let minY = Math.min(startNat.y, currentNat.y);
    let maxX = Math.max(startNat.x, currentNat.x);
    let maxY = Math.max(startNat.y, currentNat.y);

    let newW = maxX - minX;
    let newH = maxY - minY;

    // If in aspect ratio mode, constrain the drag
    if (cropMode === "aspect-ratio" && aspectRatioW > 0 && aspectRatioH > 0) {
      const ratio = aspectRatioW / aspectRatioH;
      const draggedRatio = newW / newH;

      if (draggedRatio > ratio) {
        newW = Math.round(newH * ratio);
      } else {
        newH = Math.round(newW / ratio);
      }
    }

    setFormValues(prev => prev ? {
      ...prev,
      crop_top_x: minX,
      crop_top_y: minY,
      crop_w: newW,
      crop_h: newH,
    } : null);
  }

  function handleMouseUp() {
    if (isDragging && formValues && cropMode === "aspect-ratio") {
      // Update the aspect input value to match what was dragged
      if (aspectLockDimension === "width") {
        setAspectInputValue(formValues.crop_w);
      } else {
        setAspectInputValue(formValues.crop_h);
      }
    }
    setIsDragging(false);
    setDragStart(null);
  }

  function handleCropInputChange(field: 'crop_top_x' | 'crop_top_y' | 'crop_w' | 'crop_h', value: string) {
    const numValue = value === '' ? 0 : parseInt(value, 10);
    if (isNaN(numValue) || numValue < 0) return;

    setFormValues(prev => {
      if (!prev) return null;

      let newValue = numValue;

      // Clamp values to valid ranges
      if (field === 'crop_top_x') {
        newValue = Math.min(numValue, naturalWidth - 1);
      } else if (field === 'crop_top_y') {
        newValue = Math.min(numValue, naturalHeight - 1);
      } else if (field === 'crop_w') {
        newValue = Math.min(numValue, naturalWidth - prev.crop_top_x);
      } else if (field === 'crop_h') {
        newValue = Math.min(numValue, naturalHeight - prev.crop_top_y);
      }

      return {
        ...prev,
        [field]: newValue,
      };
    });
  }

  function handleFormChange(e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const target = e.target;
    const name = target.name;
    const value = target.type === 'checkbox' ? (target as HTMLInputElement).checked : target.value;

    if (name === "crop") {
      const checked = (target as HTMLInputElement).checked;
      setCropEnabled(checked);
      if (!checked && formValues) {
        setFormValues({
          ...formValues,
          crop_top_x: 0,
          crop_top_y: 0,
          crop_w: naturalWidth,
          crop_h: naturalHeight,
        });
      }
      return;
    }

    if (name === "cropMode") {
      setCropMode(value as CropMode);
      return;
    }

    setFormValues(prev => {
      if (!prev) return null;

      let newValue: string | number | boolean | null = value;

      if (target.type === 'number') {
        newValue = value === '' ? null : parseInt(value as string, 10);
      }

      return {
        ...prev,
        [name]: newValue,
      };
    });
  }

  function handleUseImageRatio() {
    if (!formValues) return;
    const { ratioW, ratioH } = simplifyRatio(formValues.crop_w, formValues.crop_h);
    setAspectRatioW(ratioW);
    setAspectRatioH(ratioH);
  }

  function handleSelectFullImage() {
    if (!formValues) return;
    setFormValues({
      ...formValues,
      crop_top_x: 0,
      crop_top_y: 0,
      crop_w: naturalWidth,
      crop_h: naturalHeight,
    });
  }

  function handleCenterCrop() {
    if (!formValues || formValues.crop_w <= 0 || formValues.crop_h <= 0) return;
    const centerX = Math.round((naturalWidth - formValues.crop_w) / 2);
    const centerY = Math.round((naturalHeight - formValues.crop_h) / 2);
    setFormValues({
      ...formValues,
      crop_top_x: Math.max(0, centerX),
      crop_top_y: Math.max(0, centerY),
    });
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!formValues) return;

    setIsSubmitting(true);

    const sendDict: AnyDict = {
      batch_id: formValues.batch_id,
      image_id: formValues.image_id,
      type: formValues.type,
      size_type: formValues.size_type,
    };

    if (formValues.lossless) sendDict.lossless = "true";
    if (formValues.text_focus) sendDict.text_focus = "true";
    if (formValues.has_text) sendDict.has_text = "true";

    if (cropEnabled) {
      sendDict.crop_size_w = formValues.crop_size_w;
      sendDict.crop_size_h = formValues.crop_size_h;
      sendDict.crop_top_x = formValues.crop_top_x;
      sendDict.crop_top_y = formValues.crop_top_y;
      sendDict.crop_w = formValues.crop_w;
      sendDict.crop_h = formValues.crop_h;
    }

    if (formValues.width !== null && formValues.width > 0) {
      sendDict.width = formValues.width;
    }
    if (formValues.height !== null && formValues.height > 0) {
      sendDict.height = formValues.height;
    }

    const isLastJob = idx >= jobs.length - 1;

    try {
      await onSubmit(sendDict, isLastJob);

      if (!isLastJob) {
        setIdx(idx + 1);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleSkip() {
    if (idx < jobs.length - 1) {
      setIdx(idx + 1);
    }
  }

  function renderCropOverlay() {
    if (!cropEnabled || !formValues || displayWidth === 0 || displayHeight === 0) return null;

    const topLeft = naturalToDisplay(formValues.crop_top_x, formValues.crop_top_y);
    const cropW = naturalToDisplay(formValues.crop_w, 0).x;
    const cropH = naturalToDisplay(0, formValues.crop_h).y;

    const left = Math.max(0, Math.min(topLeft.x, displayWidth));
    const top = Math.max(0, Math.min(topLeft.y, displayHeight));
    const width = Math.max(0, Math.min(cropW, displayWidth - left));
    const height = Math.max(0, Math.min(cropH, displayHeight - top));

    return (
      <>
        <div className="crop-overlay-mask" style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          clipPath: `polygon(
            0% 0%, 0% 100%, 100% 100%, 100% 0%, 0% 0%,
            ${left}px ${top}px,
            ${left}px ${top + height}px,
            ${left + width}px ${top + height}px,
            ${left + width}px ${top}px,
            ${left}px ${top}px
          )`,
          pointerEvents: 'none',
        }} />
        <div className="crop-selection" style={{
          position: 'absolute',
          left: left,
          top: top,
          width: width,
          height: height,
          border: '2px dashed #00ff00',
          boxSizing: 'border-box',
          pointerEvents: 'none',
        }} />
      </>
    );
  }

  if (idx >= jobs.length) {
    return (
      <div className="submit-container">
        <h2>All Jobs Submitted!</h2>
        <p>Waiting for processing to begin...</p>
      </div>
    );
  }

  const currentJob = jobs[idx];

  return (
    <div className="submit-container">
      <div className="progress-bar">
        <span>Image {idx + 1} of {jobs.length}</span>
        <span className="original-name">{currentJob.original_name}</span>
      </div>

      <div
        ref={containerRef}
        className="image-container"
        style={{
          width: displayWidth || 'auto',
          height: displayHeight || 'auto',
          position: 'relative',
          cursor: cropEnabled ? 'crosshair' : 'default',
          margin: '0 auto',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <img
          src={currentJob.url}
          alt={currentJob.original_name}
          style={{
            width: displayWidth || 'auto',
            height: displayHeight || 'auto',
            display: 'block',
            userSelect: 'none',
            pointerEvents: 'none',
          }}
          draggable={false}
        />
        {renderCropOverlay()}
      </div>

      {formValues && (
        <form onSubmit={handleSubmit} className="submit-form">
          <div className="form-section">
            <h3>Compression Options</h3>

            <div className="form-row">
              <label>
                <input
                  type="checkbox"
                  name="lossless"
                  checked={formValues.lossless}
                  onChange={handleFormChange}
                />
                Lossless
              </label>

              <label>
                <input
                  type="checkbox"
                  name="text_focus"
                  checked={formValues.text_focus}
                  onChange={handleFormChange}
                />
                Text-Focused
              </label>

              <label>
                <input
                  type="checkbox"
                  name="has_text"
                  checked={formValues.has_text}
                  onChange={handleFormChange}
                />
                Contains Text
              </label>
            </div>

            <div className="form-row">
              <label>
                Image Type:
                <select
                  name="type"
                  value={formValues.type}
                  onChange={handleFormChange}
                >
                  <option value="default">Default</option>
                  <option value="complex">Complex (Photos)</option>
                  <option value="graphic">Graphic (Icons/Logos)</option>
                  <option value="product">Product</option>
                </select>
              </label>

              <label>
                Size Preset:
                <select
                  name="size_type"
                  value={formValues.size_type}
                  onChange={handleFormChange}
                >
                  <option value="banner">Banner</option>
                  <option value="content">Content</option>
                  <option value="thumbnail">Thumbnail</option>
                  <option value="icon">Icon</option>
                  <option value="other">Other (Custom)</option>
                </select>
              </label>
            </div>
          </div>

          <div className="form-section">
            <h3>Cropping</h3>
            <div className="form-row">
              <label>
                <input
                  type="checkbox"
                  name="crop"
                  checked={cropEnabled}
                  onChange={handleFormChange}
                />
                Enable Crop
              </label>
            </div>

            {cropEnabled && (
              <>
                <div className="form-row" style={{ marginTop: '0.75rem' }}>
                  <label>
                    <input
                      type="radio"
                      name="cropMode"
                      value="manual"
                      checked={cropMode === "manual"}
                      onChange={handleFormChange}
                    />
                    Manual Dimensions
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="cropMode"
                      value="aspect-ratio"
                      checked={cropMode === "aspect-ratio"}
                      onChange={handleFormChange}
                    />
                    Aspect Ratio
                  </label>
                </div>

                <div className="crop-controls">
                  <div className="crop-position-row">
                    <label>
                      X:
                      <input
                        type="number"
                        value={formValues.crop_top_x}
                        onChange={(e) => handleCropInputChange('crop_top_x', e.target.value)}
                        min={0}
                        max={naturalWidth - 1}
                      />
                    </label>
                    <label>
                      Y:
                      <input
                        type="number"
                        value={formValues.crop_top_y}
                        onChange={(e) => handleCropInputChange('crop_top_y', e.target.value)}
                        min={0}
                        max={naturalHeight - 1}
                      />
                    </label>
                  </div>

                  {cropMode === "manual" ? (
                    <div className="crop-size-row">
                      <label>
                        Width:
                        <input
                          type="number"
                          value={formValues.crop_w}
                          onChange={(e) => handleCropInputChange('crop_w', e.target.value)}
                          min={1}
                          max={naturalWidth - formValues.crop_top_x}
                        />
                      </label>
                      <label>
                        Height:
                        <input
                          type="number"
                          value={formValues.crop_h}
                          onChange={(e) => handleCropInputChange('crop_h', e.target.value)}
                          min={1}
                          max={naturalHeight - formValues.crop_top_y}
                        />
                      </label>
                    </div>
                  ) : (
                    <div className="aspect-ratio-controls">
                      <div className="aspect-ratio-row">
                        <label>
                          Ratio:
                          <input
                            type="number"
                            value={aspectRatioW}
                            onChange={(e) => setAspectRatioW(Math.max(1, parseInt(e.target.value) || 1))}
                            min={1}
                            style={{ width: '60px' }}
                          />
                        </label>
                        <span className="ratio-separator">:</span>
                        <input
                          type="number"
                          value={aspectRatioH}
                          onChange={(e) => setAspectRatioH(Math.max(1, parseInt(e.target.value) || 1))}
                          min={1}
                          style={{ width: '60px' }}
                        />
                        <button
                          type="button"
                          onClick={handleUseImageRatio}
                          className="secondary small"
                        >
                          Use Current
                        </button>
                      </div>
                      <div className="aspect-dimension-row">
                        <label>
                          <input
                            type="radio"
                            checked={aspectLockDimension === "width"}
                            onChange={() => setAspectLockDimension("width")}
                          />
                          Set Width:
                        </label>
                        <label>
                          <input
                            type="radio"
                            checked={aspectLockDimension === "height"}
                            onChange={() => setAspectLockDimension("height")}
                          />
                          Set Height:
                        </label>
                        <input
                          type="number"
                          value={aspectInputValue}
                          onChange={(e) => setAspectInputValue(Math.max(1, parseInt(e.target.value) || 1))}
                          min={1}
                          placeholder={aspectLockDimension === "width" ? "Width" : "Height"}
                        />
                      </div>
                    </div>
                  )}

                  <div className="crop-quick-actions">
                    <button type="button" onClick={handleSelectFullImage} className="secondary small">
                      Full Image
                    </button>
                    <button type="button" onClick={handleCenterCrop} className="secondary small">
                      Center Crop
                    </button>
                  </div>
                </div>

                <div className="crop-info">
                  <p>
                    Selection: {formValues.crop_w} × {formValues.crop_h} px
                    at ({formValues.crop_top_x}, {formValues.crop_top_y})
                  </p>
                  <p className="hint">
                    Original: {naturalWidth} × {naturalHeight} px
                    {cropMode === "aspect-ratio" && ` • Ratio: ${aspectRatioW}:${aspectRatioH}`}
                  </p>
                </div>
              </>
            )}
          </div>

          <div className="form-section">
            <h3>Custom Output Size (Optional)</h3>
            <div className="form-row">
              <label>
                Width:
                <input
                  type="number"
                  name="width"
                  value={formValues.width ?? ''}
                  onChange={handleFormChange}
                  placeholder="Auto"
                  min={1}
                />
              </label>
              <label>
                Height:
                <input
                  type="number"
                  name="height"
                  value={formValues.height ?? ''}
                  onChange={handleFormChange}
                  placeholder="Auto"
                  min={1}
                />
              </label>
            </div>
            <p className="hint">Leave empty to use size preset dimensions</p>
          </div>

          <div className="form-actions">
            <button type="button" onClick={handleSkip} disabled={isSubmitting}>
              Skip
            </button>
            <button type="submit" disabled={isSubmitting} className="primary">
              {isSubmitting ? 'Submitting...' : (idx === jobs.length - 1 ? 'Submit & Process' : 'Submit & Next')}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}