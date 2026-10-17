import { useEffect, useState } from 'react';
import { useSystemStore } from '../stores/useSystemStore';
import { getServerOrigin } from '../utils/serverOrigin';
import './CaptureReadiness.css';

export interface CaptureStatus {
  ready: boolean;
  devices: Record<string, string>;
  raw_iwr: boolean;
  mock: boolean;
}

const labels: Record<string, string> = {
  waiting: 'ready',
  capturing: 'capturing',
  processing: 'processing',
  recovering: 'recovering',
  starting: 'starting',
  unavailable: 'unavailable',
  error: 'error',
};

export function CaptureStatusBanner({ status, connected }: { status: CaptureStatus | null; connected: boolean }) {
  const ready = connected && status?.ready && Object.values(status.devices).every((state) => state === 'waiting');
  const error =
    !connected || Object.values(status?.devices ?? {}).some((state) => state === 'unavailable' || state === 'error');
  const headline = !connected
    ? 'DISCONNECTED'
    : status?.mock
      ? 'SIMULATION'
      : !status
        ? 'CHECKING RADARS'
        : ready
          ? 'READY'
          : 'WAIT';
  const detail =
    status && connected
      ? Object.entries(status.devices)
          .map(([device, state]) => `${device} ${labels[state] ?? 'checking'}`)
          .join(' · ')
      : 'Capture readiness is unknown';
  return (
    <div
      className={`capture-readiness capture-readiness--${error ? 'error' : ready ? 'ready' : 'busy'}`}
      role="status"
      aria-label="Capture readiness"
    >
      <strong>{headline}</strong>
      <span className="capture-readiness__devices">{detail}</span>
      {status?.raw_iwr && connected ? <span className="capture-readiness__recording">Raw IWR on</span> : null}
    </div>
  );
}

export function CaptureReadiness() {
  const connected = useSystemStore((state) => state.connected);
  return connected ? <ConnectedCaptureReadiness /> : <CaptureStatusBanner status={null} connected={false} />;
}

function ConnectedCaptureReadiness() {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController | undefined;
    const poll = async () => {
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 1500);
      try {
        const response = await fetch(`${getServerOrigin()}/api/capture-status`, { signal: controller.signal });
        if (!response.ok) throw new Error('Capture status unavailable');
        const snapshot = (await response.json()) as CaptureStatus;
        if (active) setStatus(snapshot);
      } catch {
        if (active) setStatus(null);
      } finally {
        clearTimeout(timeout);
        if (active) timer = setTimeout(poll, 500);
      }
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
      controller?.abort();
    };
  }, []);
  return <CaptureStatusBanner status={status} connected />;
}
