import { useEffect, useState, useRef } from 'react'
import type { Job, CompletedJob } from '../App'

type ProcessingProps = {
  batchId: number;
  totalJobs: number;
  jobs: Job[];
  onComplete: (results: CompletedJob[]) => void;
}

type PollResponse =
  | { type: 'processing' }
  | { type: 'jobs_done' }
  | { type: 'images'; batch_id: number; job_id: number; urls: string[] }
  | { type: 'job_error'; batch_id: number; job_id: number; error: string; traceback?: string };

export default function Processing({ batchId, totalJobs, jobs, onComplete }: ProcessingProps) {
  const [completedCount, setCompletedCount] = useState<number>(0);
  const [errors, setErrors] = useState<string[]>([]);
  const resultsRef = useRef<CompletedJob[]>([]);
  const pollingRef = useRef<boolean>(true);
  const completedCountRef = useRef<number>(0); // Track count in ref to avoid stale closure

  // Memoize onComplete to avoid re-running effect
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    resultsRef.current = [];
    pollingRef.current = true;
    completedCountRef.current = 0;
    setCompletedCount(0);
    setErrors([]);

    const poll = async () => {
      while (pollingRef.current) {
        try {
          const response = await fetch('/api/get-next-job', {
            method: 'GET',
            credentials: 'same-origin',
          });

          if (!response.ok) {
            console.error('Poll failed:', response.status);
            await sleep(1000);
            continue;
          }

          const data = (await response.json()) as PollResponse;

          if (data.type === 'jobs_done') {
            pollingRef.current = false;
            onCompleteRef.current(resultsRef.current);
            break;
          }

          if (data.type === 'images') {
            // Find the original name for this job
            const job = jobs.find(j => j.id === data.job_id);
            const originalName = job?.original_name ?? `image_${data.job_id}`;

            resultsRef.current.push({
              job_id: data.job_id,
              original_name: originalName,
              urls: data.urls,
            });

            completedCountRef.current += 1;
            setCompletedCount(completedCountRef.current);

            // Check if we have all results
            if (completedCountRef.current >= totalJobs) {
              pollingRef.current = false;
              onCompleteRef.current(resultsRef.current);
              break;
            }
          }

          if (data.type === 'job_error') {
            const job = jobs.find(j => j.id === data.job_id);
            const originalName = job?.original_name ?? `image_${data.job_id}`;
            setErrors(prev => [...prev, `${originalName}: ${data.error}`]);

            // Still count as "completed" for progress purposes
            completedCountRef.current += 1;
            setCompletedCount(completedCountRef.current);

            if (completedCountRef.current >= totalJobs) {
              pollingRef.current = false;
              onCompleteRef.current(resultsRef.current);
              break;
            }
          }

          if (data.type === 'processing') {
            // Still processing, wait and poll again
            await sleep(500);
          }
        } catch (err) {
          console.error('Polling error:', err);
          await sleep(1000);
        }
      }
    };

    poll();

    return () => {
      pollingRef.current = false;
    };
  }, [batchId, totalJobs, jobs]); // Removed onComplete from deps, using ref instead

  const progress = totalJobs > 0 ? Math.round((completedCount / totalJobs) * 100) : 0;

  return (
    <div className="processing-container">
      <h2>Processing Images...</h2>

      <div className="progress-wrapper">
        <div className="progress-bar-bg">
          <div
            className="progress-bar-fill"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="progress-text">
          {completedCount} / {totalJobs} ({progress}%)
        </span>
      </div>

      {errors.length > 0 && (
        <div className="error-list">
          <h3>Errors:</h3>
          <ul>
            {errors.map((err, i) => (
              <li key={i} className="error-item">{err}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="hint">
        Workers are converting your images to WebP format.
        This may take a moment depending on image size and complexity.
      </p>
    </div>
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}