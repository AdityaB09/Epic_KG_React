import { useEffect, useMemo, useRef, useState } from "react";

const MAX_REPLAY_FRAMES = 120;

export default function ECGPanel({ telemetry }) {
  const width = 640;
  const height = 150;

  const [replayMode, setReplayMode] = useState("live");
  const [replayIndex, setReplayIndex] = useState(0);
  const replayFramesRef = useRef([]);

  useEffect(() => {
    if (!telemetry) return;

    replayFramesRef.current = [
      ...replayFramesRef.current.slice(-(MAX_REPLAY_FRAMES - 1)),
      {
        time: new Date().toLocaleTimeString(),
        ecg: telemetry.ecg,
        heartRate: telemetry.heartRate,
        oxygen: telemetry.oxygen,
        systolic: telemetry.systolic,
        diastolic: telemetry.diastolic,
        respiratoryRate: telemetry.respiratoryRate,
        temperature: telemetry.temperature,
        rhythm: telemetry.rhythm,
        alert: telemetry.alert
      }
    ];

    if (replayMode === "live") {
      setReplayIndex(replayFramesRef.current.length - 1);
    }
  }, [telemetry, replayMode]);

  const replayFrames = replayFramesRef.current;

  const visibleTelemetry = useMemo(() => {
    if (replayMode === "live") return telemetry;
    return replayFrames[replayIndex] ?? telemetry;
  }, [telemetry, replayMode, replayIndex, replayFrames]);

  if (!visibleTelemetry) return null;

  const points = visibleTelemetry.ecg
    .map((point, index) => {
      const x = (index / (visibleTelemetry.ecg.length - 1)) * width;
      const y = point.y * height;
      return `${x},${y}`;
    })
    .join(" ");

  const isDanger =
    visibleTelemetry.oxygen < 92 || visibleTelemetry.heartRate > 120;

  const waveformClass =
    visibleTelemetry.rhythm === "arrhythmia"
      ? "arrhythmia"
      : visibleTelemetry.rhythm === "tachycardia"
      ? "tachycardia"
      : visibleTelemetry.rhythm === "bradycardia"
      ? "bradycardia"
      : "normal";

  return (
    <section className={`ecg-panel ${isDanger ? "danger" : ""}`}>
      <div className="ecg-header">
        <div>
          <h2>Live ECG Stream</h2>
          <p>
            {replayMode === "live"
              ? visibleTelemetry.alert
              : `Replay frame captured at ${visibleTelemetry.time}`}
          </p>
        </div>

        <span className={`live-dot ${isDanger ? "danger" : ""}`}>
          {replayMode === "live" ? "● Live" : "◷ Replay"}
        </span>
      </div>

      <div className="telemetry-grid">
        <div>
          <span>HR</span>
          <strong>{visibleTelemetry.heartRate} bpm</strong>
        </div>
        <div>
          <span>SpO₂</span>
          <strong>{visibleTelemetry.oxygen}%</strong>
        </div>
        <div>
          <span>BP</span>
          <strong>{visibleTelemetry.systolic}/{visibleTelemetry.diastolic}</strong>
        </div>
        <div>
          <span>RR</span>
          <strong>{visibleTelemetry.respiratoryRate}/min</strong>
        </div>
        <div>
          <span>Temp</span>
          <strong>{visibleTelemetry.temperature}°F</strong>
        </div>
      </div>

      <div className="ecg-stream-box">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className={`ecg-wave ${waveformClass}`}
          preserveAspectRatio="none"
        >
          <polyline points={points} />
        </svg>
      </div>

      <div className="waveform-replay-bar">
        <button
          className={replayMode === "live" ? "active" : ""}
          onClick={() => setReplayMode("live")}
        >
          Live
        </button>

        <button
          className={replayMode === "replay" ? "active" : ""}
          onClick={() => {
            setReplayMode("replay");
            setReplayIndex(Math.max(0, replayFrames.length - 30));
          }}
        >
          Replay
        </button>

        <input
          type="range"
          min="0"
          max={Math.max(0, replayFrames.length - 1)}
          value={Math.min(replayIndex, Math.max(0, replayFrames.length - 1))}
          disabled={replayMode === "live"}
          onChange={(event) => {
            setReplayMode("replay");
            setReplayIndex(Number(event.target.value));
          }}
        />

        <span>
          {replayMode === "live"
            ? "Current waveform"
            : `${replayIndex + 1}/${replayFrames.length}`}
        </span>
      </div>
    </section>
  );
}