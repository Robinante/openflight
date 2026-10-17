import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { CaptureStatusBanner, type CaptureStatus } from './CaptureReadiness';

const status: CaptureStatus = {
  ready: true,
  devices: { OPS: 'waiting', IWR: 'waiting', Camera: 'waiting' },
  raw_iwr: true,
  mock: false,
};

describe('Capture readiness', () => {
  it('shows green only while all configured workers are ready', () => {
    const html = renderToString(<CaptureStatusBanner connected status={status} />);
    expect(html).toContain('capture-readiness--ready');
    expect(html).toContain('>READY<');
    expect(html).toContain('Raw IWR on');
  });

  it.each(['capturing', 'recovering', 'processing', 'unavailable', 'error'])(
    'never shows green with IWR %s',
    (state) => {
      const html = renderToString(
        <CaptureStatusBanner
          connected
          status={{ ...status, ready: false, devices: { ...status.devices, IWR: state } }}
        />
      );
      expect(html).not.toContain('capture-readiness--ready');
      expect(html).toContain(`IWR ${state}`);
    }
  );

  it('shows unknown or disconnected instead of trusting stale readiness', () => {
    expect(renderToString(<CaptureStatusBanner connected status={null} />)).toContain('CHECKING RADARS');
    const html = renderToString(<CaptureStatusBanner connected={false} status={status} />);
    expect(html).toContain('DISCONNECTED');
    expect(html).not.toContain('capture-readiness--ready');
  });
});
