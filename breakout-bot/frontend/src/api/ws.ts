import { useEffect, useRef, useState } from "react";
import { api } from "./client";
import type { Job, JobStatus } from "./types";

type Listener = (payload: Record<string, unknown>) => void;

/** Client WebSocket unique : multiplexage par canal, reconnexion automatique. */
class WsClient {
  private ws: WebSocket | null = null;
  private listeners = new Map<string, Set<Listener>>();
  private retryMs = 1000;
  private closedByUser = false;

  private url(): string {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws`;
  }

  private ensureConnected(): void {
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) return;
    this.closedByUser = false;
    const ws = new WebSocket(this.url());
    this.ws = ws;
    ws.onopen = () => {
      this.retryMs = 1000;
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as { channel: string; payload: Record<string, unknown> };
        this.listeners.get(msg.channel)?.forEach((cb) => cb(msg.payload));
        // canaux génériques : "paper:*" etc.
        const prefix = msg.channel.split(":")[0] + ":*";
        this.listeners.get(prefix)?.forEach((cb) => cb({ ...msg.payload, __channel: msg.channel }));
      } catch {
        /* message non JSON ignoré */
      }
    };
    ws.onclose = () => {
      this.ws = null;
      if (this.closedByUser || this.listeners.size === 0) return;
      const delay = this.retryMs;
      this.retryMs = Math.min(this.retryMs * 2, 15000);
      window.setTimeout(() => this.ensureConnected(), delay);
    };
    ws.onerror = () => {
      ws.close();
    };
  }

  subscribe(channel: string, cb: Listener): () => void {
    let set = this.listeners.get(channel);
    if (!set) {
      set = new Set();
      this.listeners.set(channel, set);
    }
    set.add(cb);
    this.ensureConnected();
    return () => {
      set?.delete(cb);
      if (set && set.size === 0) this.listeners.delete(channel);
      if (this.listeners.size === 0 && this.ws) {
        this.closedByUser = true;
        this.ws.close();
        this.ws = null;
      }
    };
  }
}

export const wsClient = new WsClient();

/** Abonnement à un canal WebSocket ({channel, payload}) avec reconnexion auto. */
export function useWebSocket(channel: string | null, onMessage: Listener): void {
  const ref = useRef(onMessage);
  ref.current = onMessage;
  useEffect(() => {
    if (!channel) return;
    return wsClient.subscribe(channel, (payload) => ref.current(payload));
  }, [channel]);
}

export interface JobState {
  jobId: string;
  status: JobStatus;
  progress: number;
  error: string | null;
  result: unknown;
}

/** Suit un job long : progression via WebSocket (canal jobs:{id}) + repli par
 *  interrogation périodique de GET /api/jobs/{id} (résultat final). */
export function useJob(jobId: string | null, onDone?: (job: Job) => void): JobState | null {
  const [state, setState] = useState<JobState | null>(null);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useEffect(() => {
    if (!jobId) {
      setState(null);
      return;
    }
    let stopped = false;
    setState({ jobId, status: "en_cours", progress: 0, error: null, result: null });

    const finish = async () => {
      try {
        const job = await api.job(jobId);
        if (stopped) return;
        setState({
          jobId,
          status: job.status,
          progress: job.progress,
          error: job.error,
          result: job.result,
        });
        if (job.status !== "en_cours") doneRef.current?.(job);
        return job.status !== "en_cours";
      } catch {
        return false;
      }
    };

    const unsub = wsClient.subscribe(`jobs:${jobId}`, (payload) => {
      if (stopped) return;
      const status = (payload.status as JobStatus) ?? "en_cours";
      const progress = typeof payload.progress === "number" ? payload.progress : 0;
      if (status === "en_cours") {
        setState((s) => (s ? { ...s, status, progress } : s));
      } else {
        void finish();
      }
    });

    const interval = window.setInterval(async () => {
      const terminal = await finish();
      if (terminal) window.clearInterval(interval);
    }, 2500);

    return () => {
      stopped = true;
      unsub();
      window.clearInterval(interval);
    };
  }, [jobId]);

  return state;
}
