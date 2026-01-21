import { useState } from 'react'
import type { CompletedJob } from '../App'

type DownloadProps = {
  job: CompletedJob;
  currentIndex: number;
  totalJobs: number;
  onNext: () => void;
  onReset: () => void;
}

export default function Download({ job, currentIndex, totalJobs, onNext, onReset }: DownloadProps) {
  const [selectedIdx, setSelectedIdx] = useState<number>(0);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);

  // Get the base name without extension for the download filename
  const baseName = job.original_name.replace(/\.[^/.]+$/, '');

  async function handleDownload() {
    if (job.urls.length === 0) return;

    setIsDownloading(true);

    try {
      const url = job.urls[selectedIdx];
      const response = await fetch(url);
      const blob = await response.blob();

      // Create download link
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `${baseName}.webp`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);

      // Automatically go to next after download
      setTimeout(() => {
        onNext();
      }, 500);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Download failed. Please try again.');
    } finally {
      setIsDownloading(false);
    }
  }

  function handleSkip() {
    onNext();
  }

  const isLastJob = currentIndex >= totalJobs - 1;

  return (
    <div className="download-container">
      <div className="progress-bar">
        <span>Download {currentIndex + 1} of {totalJobs}</span>
        <span className="original-name">{job.original_name}</span>
      </div>

      {job.urls.length === 0 ? (
        <div className="no-results">
          <p>No conversion results available for this image.</p>
          <button onClick={onNext}>
            {isLastJob ? 'Finish' : 'Next Image'}
          </button>
        </div>
      ) : (
        <>
          <div className="variant-grid">
            {job.urls.map((url, idx) => (
              <div
                key={idx}
                className={`variant-card ${selectedIdx === idx ? 'selected' : ''}`}
                onClick={() => setSelectedIdx(idx)}
              >
                <img
                  src={url}
                  alt={`Variant ${idx + 1}`}
                  loading="lazy"
                />
                <span className="variant-label">Variant {idx + 1}</span>
              </div>
            ))}
          </div>

          <div className="download-preview">
            <h3>Selected: Variant {selectedIdx + 1}</h3>
            <img
              src={job.urls[selectedIdx]}
              alt="Selected variant preview"
              className="preview-image"
            />
          </div>

          <div className="download-actions">
            <button onClick={handleSkip} disabled={isDownloading}>
              Skip
            </button>
            <button
              onClick={handleDownload}
              disabled={isDownloading}
              className="primary"
            >
              {isDownloading ? 'Downloading...' : `Download as ${baseName}.webp`}
            </button>
          </div>

          <p className="hint">
            Click on a variant to preview it, then download your preferred version.
            {!isLastJob && ' The next image will appear after download.'}
          </p>
        </>
      )}

      {isLastJob && (
        <div className="finish-section">
          <button onClick={onReset} className="secondary">
            Start Over with New Images
          </button>
        </div>
      )}
    </div>
  );
}