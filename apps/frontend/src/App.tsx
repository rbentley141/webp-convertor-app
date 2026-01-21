import { useState } from 'react'

import './App.css'
import Upload from './components/Upload'
import Submit from './components/Submit'
import Download from './components/Download'
import Processing from './components/Processing'


type Modes = "upload" | "submit" | "download" | "processing";

export type Job = {
  id: number;
  url: string;
  original_name: string;
}

export type UploadZipResponse = {
  batch_id: number;
  images: Job[];
}

export type CompletedJob = {
  job_id: number;
  original_name: string;
  urls: string[];
}

export type AnyDict = Record<string, string | number | boolean>;


function App() {
  const [status, setStatus] = useState<Modes>("upload")
  const [batchId, setBatchId] = useState<number | null>(null)
  const [images, setImages] = useState<Job[]>([])
  const [totalJobs, setTotalJobs] = useState<number>(0)
  const [completedJobs, setCompletedJobs] = useState<CompletedJob[]>([])
  const [currentDownloadIdx, setCurrentDownloadIdx] = useState<number>(0)

  async function handleFileUpload(file: File) : Promise<void> {
    const formData = new FormData();
    formData.append("file", file);

    const r = await fetch("/api/upload-zip", {
      "method": "POST",
      "credentials": "same-origin",
      body: formData
    })
    
    if (!r.ok) {
      const err = await r.json();
      alert(`Upload failed: ${err.description || 'Unknown error'}`);
      return;
    }

    const json = (await r.json()) as UploadZipResponse;

    // BUG FIX: The backend returns images with job_id, not id
    // Map them correctly
    const mappedImages: Job[] = json.images.map((img: any) => ({
      id: img.job_id,
      url: img.url,
      original_name: img.original_name,
    }));

    setBatchId(json.batch_id)
    setImages(mappedImages)
    setTotalJobs(mappedImages.length)
    setCompletedJobs([])
    setCurrentDownloadIdx(0)
    setStatus("submit")
  };

  async function handleJobSubmit(formData: AnyDict, isLastJob: boolean): Promise<void>{
    const form = new FormData()
    for (const [key, value] of Object.entries(formData)) {
      if (value !== null && value !== undefined) {
        form.append(key, String(value));
      }
    }
    const r = await fetch("/api/submit-job", {
      method: "POST",
      credentials: "same-origin",
      body: form
    });

    if (!r.ok) {
      const err = await r.json();
      console.error("Job submit failed:", err);
      alert(`Job submission failed: ${err.description || 'Unknown error'}`);
      return;
    }

    if (isLastJob) {
      setStatus("processing")
    }
  }

  async function handleProcessingComplete(results: CompletedJob[]): Promise<void> {
    setCompletedJobs(results)
    setCurrentDownloadIdx(0)
    setStatus("download")
  }

  function handleDownloadNext(): void {
    if (currentDownloadIdx < completedJobs.length - 1) {
      setCurrentDownloadIdx(currentDownloadIdx + 1)
    } else {
      handleReset()
    }
  }

  function handleReset(): void {
    setStatus("upload")
    setBatchId(null)
    setImages([])
    setTotalJobs(0)
    setCompletedJobs([])
    setCurrentDownloadIdx(0)
  }
  return (
    <div className="app-container">
      <h1>WebPForge</h1>
      <p className="subtitle">WebP Conversion</p>

      {status === "upload" && (
        <Upload onSubmit={handleFileUpload} />
      )}

      {status === "submit" && batchId !== null && (
        <Submit
          onSubmit={handleJobSubmit}
          batch_id={batchId}
          jobs={images}
        />
      )}

      {status === "processing" && batchId !== null && (
        <Processing
          batchId={batchId}
          totalJobs={totalJobs}
          jobs={images}
          onComplete={handleProcessingComplete}
        />
      )}

      {status === "download" && completedJobs.length > 0 && (
        <Download
          job={completedJobs[currentDownloadIdx]}
          currentIndex={currentDownloadIdx}
          totalJobs={completedJobs.length}
          onNext={handleDownloadNext}
          onReset={handleReset}
        />
      )}
    </div>
  )
}

export default App