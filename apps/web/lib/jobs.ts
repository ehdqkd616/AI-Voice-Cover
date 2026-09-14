import { api } from "./api-client";
import { translateError } from "./errors";

/** Resolves with the job's output media ids once it succeeds, or rejects with
 * a Korean-friendly message once it fails. Lets callers `await` a job inline
 * instead of juggling per-step component state. */
export function waitForJob(jobId: string): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const source = new EventSource(api.jobEventsUrl(jobId));
    let done = false;

    source.addEventListener("complete", (e) => {
      if (done) return;
      done = true;
      const data = JSON.parse((e as MessageEvent).data);
      source.close();
      resolve((data.outputs ?? []).map((o: { media_id: string }) => o.media_id));
    });

    source.addEventListener("error", (e) => {
      if (done) return;
      done = true;
      const data = (e as MessageEvent).data ? JSON.parse((e as MessageEvent).data) : {};
      source.close();
      reject(new Error(translateError(data.code, data.message)));
    });
  });
}
