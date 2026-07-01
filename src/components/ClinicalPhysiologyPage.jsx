import { useEffect, useMemo, useState } from "react";
import "./ClinicalPhysiologyPage.css";
import { connectFhirStream } from "../services/fhirStream";


const MAX_POINTS = 360;
const CURRENT_MARK_RATIO = 0.47;

const BASE_PATIENT = {
  name: "Leslie Abbott",
  sex: "FEMALE",
  dob: "1946-08-22",
  id: "87675858"
};

function formatLiveClock(date = new Date()) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
}

const MEDICATION_ROWS = [
  {
    med: "Simvastatin",
    sub: "Bedtime",
    dose: "5mg",
    taken: [{ ok: true, time: "20:00" }],
    date: "07/16/25"
  },
  {
    med: "Spironolactone",
    sub: "q12hr",
    dose: "25mg",
    taken: [
      { ok: true, time: "08:00" },
      { ok: false, time: "20:00" }
    ],
    date: "07/16/25"
  },
  {
    med: "Oral Temperature",
    sub: "",
    dose: "37.2",
    warning: true,
    taken: [{ ok: false, time: "20:00" }],
    date: "07/10/25"
  }
];

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function appendValues(series, values) {
  return [...series.slice(values.length), ...values];
}

function buildStrip(factory, tick = 0) {
  return Array.from({ length: MAX_POINTS }, (_, index) => factory(index, tick));
}

function ecgValue(index, tick = 0) {
  const crisisStart = Math.floor(MAX_POINTS * CURRENT_MARK_RATIO);
  const animatedIndex = index + tick * 1.8;
  const beat = (animatedIndex * 0.083) % 1;

  let value = 0.5 + Math.sin(animatedIndex * 0.035) * 0.015;

  if (index < crisisStart) {
    if (beat < 0.025) value = 0.5;
    else if (beat < 0.043) value = 0.62;
    else if (beat < 0.058) value = 0.25;
    else if (beat < 0.076) value = 0.91;
    else if (beat < 0.11) value = 0.43;
    else if (beat < 0.22) value = 0.52 + Math.sin(beat * Math.PI * 6) * 0.045;
    else value = 0.5 + Math.sin(animatedIndex * 0.1) * 0.018;
  } else {
    const wideBeat = (animatedIndex * 0.038) % 1;
    value =
      0.5 +
      Math.sin(wideBeat * Math.PI * 2) * 0.31 +
      Math.sin(animatedIndex * 0.24) * 0.055;
  }

  return clamp(value, 0.08, 0.95);
}

function redRhythmValue(index, tick = 0) {
  const crisisStart = Math.floor(MAX_POINTS * CURRENT_MARK_RATIO);
  const animatedIndex = index + tick * 1.6;
  const beat = (animatedIndex * 0.085) % 1;

  let value = 0.5 + Math.sin(animatedIndex * 0.04) * 0.012;

  if (index < crisisStart) {
    if (beat < 0.03) value = 0.5;
    else if (beat < 0.047) value = 0.62;
    else if (beat < 0.06) value = 0.34;
    else if (beat < 0.078) value = 0.74;
    else if (beat < 0.13) value = 0.48;
  } else {
    value =
      0.5 +
      Math.sin(animatedIndex * 0.18) * 0.18 +
      Math.sin(animatedIndex * 0.42) * 0.035;
  }

  return clamp(value, 0.12, 0.88);
}

function ppgValue(index, tick = 0, soft = false) {
  const crisisStart = Math.floor(MAX_POINTS * CURRENT_MARK_RATIO);
  const animatedIndex = index + tick * 1.4;
  const beat = (animatedIndex * 0.058) % 1;

  let pulse =
    beat < 0.11
      ? Math.sin((beat / 0.11) * Math.PI) * 0.58
      : Math.exp(-beat * 4.8) * 0.23;

  if (soft) pulse *= 0.62;

  let value = 0.34 + pulse + Math.sin(animatedIndex * 0.055) * 0.018;

  if (index > crisisStart) {
    value += Math.sin(animatedIndex * 0.35) * 0.045;
  }

  return clamp(value, 0.08, 0.94);
}

function buildSeries(factory) {
  return Array.from({ length: MAX_POINTS }, (_, index) => factory(index));
}

const DEFAULT_ALERT_INTERPRETATION = {
  title: "(!) Critical abnormalities detected",
  rhythm:
    "Sinus rhythm with peaked T waves progressing to QRS widening, sine-wave morphology with loss of P waves, agonal complexes, and ventricular fibrillation.",
  ppg:
    "Normal pulsatile waveform with dicrotic notch, degrading amplitude, lasting to ventricular fibrillation onset.",
  likelyEtiology:
    "Hyperkalemic arrest in a patient on spironolactone with history of intermittent hyperkalemia, possibly precipitated by drug interaction, drug overdose, or recent renal impairment during K+ to lethal levels."
};

function appendOne(series, value, max = 8) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return series;
  }

  return [...series, Number(value)].slice(-max);
}

function normalizeColor(color, fallback = "blue") {
  if (color === "red" || color === "yellow" || color === "blue") {
    return color;
  }

  return fallback;
}

function statusFromColor(color) {
  if (color === "red") return "High/Critical";
  if (color === "yellow") return "Warning";
  return "Stable";
}

function formatStreamDate(timestamp) {
  if (!timestamp) return "07/16/25";

  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return "07/16/25";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "2-digit"
  }).format(date);
}

function mergeFirelyFrameIntoLive(prev, frame) {
  if (!frame) return prev;

  if (frame.status === "error" || frame.error) {
    return {
      ...prev,
      firelyStatus: "error",
      alertColor: "yellow",
      alertInterpretation: frame.interpretation || {
        title: "Firely stream warning",
        rhythm: "The dashboard could not fetch the latest Firely Observations.",
        ppg: "Local waveform simulation is still running.",
        likelyEtiology: "Check whether the FastAPI backend is running on port 8000."
      }
    };
  }

  const vitals = frame.vitals || {};
  const labs = frame.labs || {};
  const colors = frame.colors || {};

  const next = {
    ...prev,
    firelyStatus: frame.status || "connected",
    firelySource: frame.source || "firely-public-sandbox",
    streamTimestamp: frame.timestamp || frame.receivedAt,
    fallbackUsed: frame.fallbackUsed || [],


  priorityTrends: frame.priorityTrends || prev.priorityTrends || [],
  medicationRows: frame.medicationRows || prev.medicationRows || MEDICATION_ROWS,
  contextAlerts: frame.contextAlerts || prev.contextAlerts || [],


    alertColor: normalizeColor(frame.overallColor || frame.color, prev.alertColor || "red"),
    alertInterpretation: frame.interpretation || prev.alertInterpretation,

    colors: {
      ...prev.colors,
      ...colors
    },

    heartRate: vitals.heartRate ?? prev.heartRate,
    respiratoryRate: vitals.respiratoryRate ?? prev.respiratoryRate,
    spo2: vitals.spo2 ?? prev.spo2,
    systolic: vitals.systolic ?? prev.systolic,
    diastolic: vitals.diastolic ?? prev.diastolic,
    temperature: vitals.temperature ?? prev.temperature,

    glucose: labs.glucose ?? prev.glucose,
    potassium: labs.potassium ?? prev.potassium,
    creatinine: labs.creatinine ?? prev.creatinine,
    wbc: labs.wbc ?? prev.wbc
  };

  return {
    ...next,
    heartTrend: appendOne(prev.heartTrend, next.heartRate),
    respTrend: appendOne(prev.respTrend, next.respiratoryRate),
    spo2Trend: appendOne(prev.spo2Trend, next.spo2),
    glucoseTrend: appendOne(prev.glucoseTrend, next.glucose),
    potassiumTrend: appendOne(prev.potassiumTrend, next.potassium),
    creatinineTrend: appendOne(prev.creatinineTrend, next.creatinine),
    wbcTrend: appendOne(prev.wbcTrend, next.wbc)
  };
}

function getLiveColor(live, field, fallback = "blue") {
  return normalizeColor(live.colors?.[field], fallback);
}

function createInitialLiveState() {
  return {
    tick: 0,
    clockText: formatLiveClock(),
    heartRate: 160,
    respiratoryRate: 35,
    spo2: 99,
    systolic: 130,
    diastolic: 85,
    temperature: 37.2,
    glucose: 225,
    potassium: 5.4,
    creatinine: 1.42,
    wbc: 12.1,
    ecg: buildStrip(ecgValue, 0),
    resp: buildStrip(redRhythmValue, 0),
    ppg: buildStrip((index, tick) => ppgValue(index, tick, false), 0),
    ppgSoft: buildStrip((index, tick) => ppgValue(index, tick, true), 0),
    heartTrend: [122, 130, 139, 148, 160],
    respTrend: [18, 21, 24, 29, 35],
    spo2Trend: [97, 98, 97, 99, 99],
    glucoseTrend: [125, 139, 141, 205, 225],
    potassiumTrend: [3.9, 4.2, 4.6, 5.1, 5.4],
    creatinineTrend: [0.89, 0.96, 1.05, 1.23, 1.42],
    wbcTrend: [8.2, 9.1, 10.4, 11.2, 12.1],
    firelyStatus: "local",
firelySource: "local-simulation",
streamTimestamp: null,
fallbackUsed: [],
priorityTrends: [],
medicationRows: MEDICATION_ROWS,
alertColor: "red",
alertInterpretation: DEFAULT_ALERT_INTERPRETATION,
colors: {
  heartRate: "red",
  respiratoryRate: "yellow",
  spo2: "blue",
  systolic: "blue",
  diastolic: "blue",
  temperature: "yellow",
  glucose: "red",
  potassium: "red",
  creatinine: "red",
  wbc: "red"
}
  };
}

function nextLiveState(prev) {
  const tick = prev.tick + 1;
  const usingFirely = prev.firelyStatus === "connected";

  const simulatedHeartRate = Math.round(
    clamp(160 + Math.sin(tick / 4) * 7 + Math.sin(tick / 11) * 4, 146, 174)
  );

  const simulatedRespiratoryRate = Math.round(
    clamp(35 + Math.sin(tick / 5) * 3 + Math.sin(tick / 13) * 2, 29, 40)
  );

  const simulatedSpo2 = Math.round(
    clamp(98.5 + Math.sin(tick / 7) * 1.2, 96, 100)
  );

  const simulatedSystolic = Math.round(
    clamp(130 + Math.sin(tick / 8) * 4, 124, 138)
  );

  const simulatedDiastolic = Math.round(
    clamp(85 + Math.sin(tick / 9) * 3, 80, 90)
  );

  const simulatedTemperature = Number(
    clamp(37.2 + Math.sin(tick / 10) * 0.15, 37.0, 37.5).toFixed(1)
  );

  const simulatedGlucose = Math.round(
    clamp(225 + Math.sin(tick / 6) * 9, 214, 238)
  );

  const simulatedPotassium = Number(
    clamp(5.4 + Math.sin(tick / 8) * 0.15, 5.2, 5.7).toFixed(1)
  );

  const simulatedCreatinine = Number(
    clamp(1.42 + Math.sin(tick / 9) * 0.06, 1.34, 1.52).toFixed(2)
  );

  const simulatedWbc = Number(
    clamp(12.1 + Math.sin(tick / 7) * 0.5, 11.4, 12.9).toFixed(1)
  );

  const heartRate = usingFirely ? prev.heartRate : simulatedHeartRate;
  const respiratoryRate = usingFirely ? prev.respiratoryRate : simulatedRespiratoryRate;
  const spo2 = usingFirely ? prev.spo2 : simulatedSpo2;
  const systolic = usingFirely ? prev.systolic : simulatedSystolic;
  const diastolic = usingFirely ? prev.diastolic : simulatedDiastolic;
  const temperature = usingFirely ? prev.temperature : simulatedTemperature;
  const glucose = usingFirely ? prev.glucose : simulatedGlucose;
  const potassium = usingFirely ? prev.potassium : simulatedPotassium;
  const creatinine = usingFirely ? prev.creatinine : simulatedCreatinine;
  const wbc = usingFirely ? prev.wbc : simulatedWbc;

  const nextState = {
    ...prev,
    tick,
    clockText: formatLiveClock(),

    heartRate,
    respiratoryRate,
    spo2,
    systolic,
    diastolic,
    temperature,
    glucose,
    potassium,
    creatinine,
    wbc,

    ecg: buildStrip(ecgValue, tick),
    resp: buildStrip(redRhythmValue, tick),
    ppg: buildStrip((index, currentTick) => ppgValue(index, currentTick, false), tick),
    ppgSoft: buildStrip((index, currentTick) => ppgValue(index, currentTick, true), tick)
  };

  if (usingFirely) {
    return nextState;
  }

  return {
    ...nextState,
    heartTrend: appendValues(prev.heartTrend, [heartRate]).slice(-8),
    respTrend: appendValues(prev.respTrend, [respiratoryRate]).slice(-8),
    spo2Trend: appendValues(prev.spo2Trend, [spo2]).slice(-8),
    glucoseTrend: appendValues(prev.glucoseTrend, [glucose]).slice(-8),
    potassiumTrend: appendValues(prev.potassiumTrend, [potassium]).slice(-8),
    creatinineTrend: appendValues(prev.creatinineTrend, [creatinine]).slice(-8),
    wbcTrend: appendValues(prev.wbcTrend, [wbc]).slice(-8)
  };
}

function toPolylineNormalized(values, width, height, padding = 6) {
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - padding - value * (height - padding * 2);
      return `${x},${clamp(y, padding, height - padding)}`;
    })
    .join(" ");
}

function toPolylineScaled(values, width = 80, height = 34, padding = 4) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - padding - ((value - min) / range) * (height - padding * 2);
      return `${x},${clamp(y, padding, height - padding)}`;
    })
    .join(" ");
}

function WaveChart({
  label,
  color,
  values,
  compact = false,
  currentTime = false,
  clockText,
  onOpen,
  ariaLabel
}) {
  const width = 620;
  const height = compact ? 42 : 66;
  const ChartTag = onOpen ? "button" : "div";

  return (
    <ChartTag
      type={onOpen ? "button" : undefined}
      className={`kgen-wave-card ${compact ? "compact" : ""} ${color} ${
        onOpen ? "kgen-clickable-wave" : ""
      }`}
      onClick={onOpen}
      aria-label={ariaLabel}
    >
      {label && <span className={`kgen-wave-label ${color}`}>{label}</span>}

      {currentTime && (
        <>
          <span className="kgen-current-marker" />
          <span className="kgen-current-time">
            Current time: {clockText || formatLiveClock()}
          </span>
        </>
      )}

      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <polyline points={toPolylineNormalized(values, width, height)} />
      </svg>

      {onOpen && <span className="kgen-open-wave-hint">↗</span>}
    </ChartTag>
  );
}

function MiniTrend({ values, color = "red", onOpen, ariaLabel }) {
  const TrendTag = onOpen ? "button" : "div";

  return (
    <TrendTag
      type={onOpen ? "button" : undefined}
      className={`kgen-mini-trend-box ${color} ${
        onOpen ? "kgen-clickable-trend" : ""
      }`}
      onClick={onOpen}
      aria-label={ariaLabel}
    >
      <svg
        className={`kgen-mini-trend ${color}`}
        viewBox="0 0 80 34"
        preserveAspectRatio="none"
      >
        <polyline points={toPolylineScaled(values)} />
      </svg>

      {onOpen && <span className="kgen-mini-open-dot">↗</span>}
    </TrendTag>
  );
}

function LabTile({
  name,
  value,
  status,
  meta,
  trend,
  color = "red",
  onOpenTrend
}) {
  const [firstDate = "06/23", secondDate = "07/18"] = String(
    meta || "06/23 07/18"
  ).split(" ");

  return (
    <article className={`kgen-lab-tile ${color}`}>
      <div className="kgen-lab-title">
        <span>{name}</span>

        <button
          type="button"
          aria-label={`Open ${name} lab trend`}
          onClick={onOpenTrend}
        >
          ›
        </button>
      </div>

      <div className="kgen-lab-value-row">
        <div className="kgen-lab-reading">
          <strong>{value}</strong>
          <small>{status}</small>
        </div>

        <div className="kgen-lab-spark-wrap">
          <MiniTrend
            values={trend}
            color={color}
            onOpen={onOpenTrend}
            ariaLabel={`Open ${name} trend popup`}
          />

          <div className="kgen-lab-spark-dates">
            <span>{firstDate}</span>
            <span>{secondDate}</span>
          </div>
        </div>
      </div>
    </article>
  );
}
function WaveformOverlay({ config, onClose }) {
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleKeyDown);
    document.body.classList.add("kgen-wave-modal-open");

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.classList.remove("kgen-wave-modal-open");
    };
  }, [onClose]);

  if (!config) return null;

  const width = 980;
  const height = 340;

  const points =
    config.scaleMode === "scaled"
      ? toPolylineScaled(config.values, width, height, 24)
      : toPolylineNormalized(config.values, width, height, 24);

  const minValue = Math.min(...config.values);
  const maxValue = Math.max(...config.values);
  const latestValue = config.values[config.values.length - 1];

  return (
    <div className="kgen-wave-overlay-backdrop" onMouseDown={onClose}>
      <section
        className="kgen-wave-overlay-card"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={config.title}
      >
        <header className="kgen-wave-overlay-header">
          <div>
            <p>{config.section}</p>
            <h2>{config.title}</h2>
            <span>{config.subtitle}</span>
          </div>

          <button
            type="button"
            className="kgen-wave-overlay-close"
            onClick={onClose}
            aria-label="Close waveform popup"
          >
            ×
          </button>
        </header>

        <div className="kgen-wave-overlay-stats">
          <div>
            <span>Current</span>
            <strong>
              {config.currentValue}
              {config.unit}
            </strong>
          </div>

          <div>
            <span>Status</span>
            <strong>{config.status}</strong>
          </div>

          <div>
            <span>Min</span>
            <strong>
              {config.scaleMode === "scaled" ? minValue.toFixed(config.decimals ?? 0) : "Live"}
            </strong>
          </div>

          <div>
            <span>Max</span>
            <strong>
              {config.scaleMode === "scaled" ? maxValue.toFixed(config.decimals ?? 0) : "Live"}
            </strong>
          </div>
        </div>

        <div className={`kgen-wave-overlay-chart ${config.color}`}>
          <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
            <polyline points={points} />
          </svg>
        </div>

        <footer className="kgen-wave-overlay-footer">
          <span>{config.footerLeft}</span>
          <span>{config.footerRight}</span>
        </footer>
      </section>
    </div>
  );
}

export default function ClinicalPhysiologyPage({ patient, onOpenLabs }) {
  const [live, setLive] = useState(createInitialLiveState);
  const [activeWaveformId, setActiveWaveformId] = useState(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setLive((prev) => nextLiveState(prev));
    }, 420);

    return () => clearInterval(interval);
  }, []);

useEffect(() => {
  const provider = "oracle";

  console.log("[KGEN FHIR STREAM CONFIG]", {
  provider,
  streamUrl: import.meta.env.VITE_FHIR_STREAM_URL,
  envPatientId: import.meta.env.VITE_FHIR_PATIENT_ID
});

  const streamPatientId = "";

  const disconnect = connectFhirStream({
    provider,
    patientId: streamPatientId,
    onFrame: (frame) => {
  console.log("[KGEN PAGE FRAME RECEIVED]", {
    source: frame.source,
    status: frame.status,
    receivedAt: frame.receivedAt,
    fhirFields: frame.dataQuality?.fhirFields,
    fallbackFields: frame.dataQuality?.fallbackFields,
    observationCount: frame.dataQuality?.observationCount,
    matchedObservationCount: frame.dataQuality?.matchedObservationCount,
    vitals: frame.vitals,
    labs: frame.labs
  });

  setLive((prev) => mergeFirelyFrameIntoLive(prev, frame));
},
    onHeartbeat: () => {
      setLive((prev) => ({
        ...prev,
        firelyStatus:
          prev.firelyStatus === "local" ? "connecting" : prev.firelyStatus
      }));
    },
    onError: () => {
      setLive((prev) => ({
        ...prev,
        firelyStatus: "error",
        alertColor: "yellow",
        alertInterpretation: {
          title: "FHIR stream warning",
          rhythm: "The dashboard could not receive the latest FHIR stream frame.",
          ppg: "Local waveform simulation is still running.",
          likelyEtiology: "Check whether FastAPI is running on http://127.0.0.1:8000."
        }
      }));
    }
  });

  return disconnect;
}, [patient?.fhirId, patient?.id]);

  const currentPatient = useMemo(() => {
    if (!patient) return BASE_PATIENT;

    return {
      name: patient.name || BASE_PATIENT.name,
      sex: patient.sex?.toUpperCase?.() || BASE_PATIENT.sex,
      dob: BASE_PATIENT.dob,
      id: patient.mrn || patient.id || BASE_PATIENT.id
    };
  }, [patient]);

const streamDate = formatStreamDate(live.streamTimestamp);

const labCards = useMemo(() => {
  if (live.priorityTrends?.length) {
    return live.priorityTrends.map((item) => ({
      name: item.label,
      value: item.displayValue ?? item.value,
      status: statusFromColor(normalizeColor(item.color, "blue")),
      meta: item.meta || streamDate,
      trend: item.trend || [],
      color: normalizeColor(item.color, "blue"),
      reason: item.reason
    }));
  }

  return [
    {
      name: "Glucose",
      value: live.glucose,
      status: statusFromColor(getLiveColor(live, "glucose", "red")),
      meta: streamDate,
      trend: live.glucoseTrend,
      color: getLiveColor(live, "glucose", "red")
    },
    {
      name: "Potassium",
      value: Number(live.potassium).toFixed(1),
      status: statusFromColor(getLiveColor(live, "potassium", "red")),
      meta: streamDate,
      trend: live.potassiumTrend,
      color: getLiveColor(live, "potassium", "red")
    },
    {
      name: "Creatinine",
      value: Number(live.creatinine).toFixed(2),
      status: statusFromColor(getLiveColor(live, "creatinine", "red")),
      meta: streamDate,
      trend: live.creatinineTrend,
      color: getLiveColor(live, "creatinine", "red")
    },
    {
      name: "WBC",
      value: Number(live.wbc).toFixed(1),
      status: statusFromColor(getLiveColor(live, "wbc", "red")),
      meta: streamDate,
      trend: live.wbcTrend,
      color: getLiveColor(live, "wbc", "red")
    }
  ];
}, [
  live.priorityTrends,
  live.glucose,
  live.potassium,
  live.creatinine,
  live.wbc,
  live.glucoseTrend,
  live.potassiumTrend,
  live.creatinineTrend,
  live.wbcTrend,
  live.colors,
  streamDate
]);

const vitalRows = [
  ["BP", `${live.systolic}/${live.diastolic}`, "mmHg", streamDate],
  ["SpO2", live.spo2, "%", streamDate],
  ["Oral Temperature", Number(live.temperature).toFixed(1), "°C", streamDate]
];

  const waveformOverlay = useMemo(() => {
    if (!activeWaveformId) return null;

    const liveWaveforms = {
      ecg: {
        section: "01. Live Physiology",
        title: "ECG waveform",
        subtitle: `${currentPatient.name} • Hyperkalemic rhythm progression`,
        scaleMode: "normalized",
        values: live.ecg,
        currentValue: live.heartRate,
        unit: " bpm",
        status: "Critical",
        footerLeft: "0s",
        footerRight: "16s",
         color: getLiveColor(live, "heartRate", live.alertColor || "red")
      },
      resp: {
        section: "01. Live Physiology",
        title: "Respiratory rhythm waveform",
        subtitle: `${currentPatient.name} • Respiratory waveform strip`,
       color: getLiveColor(live, "respiratoryRate", "yellow"),
        scaleMode: "normalized",
        values: live.resp,
        currentValue: live.respiratoryRate,
        unit: " rpm",
        status: "Warning",
        footerLeft: "0s",
        footerRight: "16s"
      },
      ppg: {
        section: "01. Live Physiology",
        title: "PPG waveform",
        subtitle: `${currentPatient.name} • Pulse plethysmography signal`,
        color: getLiveColor(live, "spo2", "blue"),
        scaleMode: "normalized",
        values: live.ppg,
        currentValue: live.spo2,
        unit: "%",
        status: "Monitored",
        footerLeft: "0s",
        footerRight: "16s"
      },
      ppgSoft: {
        section: "01. Live Physiology",
        title: "Secondary PPG waveform",
        subtitle: `${currentPatient.name} • Low amplitude pulse trend`,
        color: getLiveColor(live, "spo2", "blue"),
        scaleMode: "normalized",
        values: live.ppgSoft,
        currentValue: live.spo2,
        unit: "%",
        status: "Monitored",
        footerLeft: "0s",
        footerRight: "16s"
      },
      heartTrend: {
        section: "01. Live Physiology",
        title: "Heart rate trend",
        subtitle: `${currentPatient.name} • Live heart rate mini trend`,
        color: getLiveColor(live, "heartRate", "red"),
        scaleMode: "scaled",
        values: live.heartTrend,
        currentValue: live.heartRate,
        unit: " bpm",
        status: "Critical",
        decimals: 0,
        footerLeft: "Earlier",
        footerRight: "Now"
      },
      respTrend: {
        section: "01. Live Physiology",
        title: "Respiratory rate trend",
        subtitle: `${currentPatient.name} • Live respiratory trend`,
          color: getLiveColor(live, "respiratoryRate", "yellow"),
        scaleMode: "scaled",
        values: live.respTrend,
        currentValue: live.respiratoryRate,
        unit: " rpm",
        status: "Warning",
        decimals: 0,
        footerLeft: "Earlier",
        footerRight: "Now"
      },
      spo2Trend: {
        section: "01. Live Physiology",
        title: "SpO2 trend",
        subtitle: `${currentPatient.name} • Oxygen saturation trend`,
         color: getLiveColor(live, "spo2", "blue"),
        scaleMode: "scaled",
        values: live.spo2Trend,
        currentValue: live.spo2,
        unit: "%",
        status: "Stable",
        decimals: 0,
        footerLeft: "Earlier",
        footerRight: "Now"
      }
    };

    if (liveWaveforms[activeWaveformId]) {
      return liveWaveforms[activeWaveformId];
    }

    const labName = activeWaveformId.replace("lab-", "");
    const selectedLab = labCards.find((item) => item.name === labName);
    
  


    if (!selectedLab) return null;

    return {
      section: "03. Recent Lab Results & Trends",
      title: `${selectedLab.name} trend`,
      subtitle: `${currentPatient.name} • Lab trend over recent draws`,
      color: selectedLab.color || "red",
      scaleMode: "scaled",
      values: selectedLab.trend,
      currentValue: selectedLab.value,
      unit: "",
      status: selectedLab.status,
      decimals:
        selectedLab.name === "Creatinine"
          ? 2
          : selectedLab.name === "Potassium"
          ? 1
          : selectedLab.name === "WBC"
          ? 1
          : 0,
      footerLeft: "06/23",
      footerRight: "07/18"
    };
  }, [activeWaveformId, currentPatient.name, live, labCards]);

const interpretation =
  live.alertInterpretation || DEFAULT_ALERT_INTERPRETATION;

const alertColor = normalizeColor(live.alertColor, "red");


  return (
    <section className="kgen-page">
      <header className="kgen-topbar">
        <div className="kgen-brand-box">
          <div className="kgen-logo">⌁</div>
          <span>KardioGenics</span>
        </div>

        <div className="kgen-patient-box">
          <strong>{currentPatient.name}</strong>
          <span>
            {currentPatient.sex} | DOB: {currentPatient.dob} | ID: {currentPatient.id}
          </span>
        </div>

        <div className="kgen-title-box">
  <span>CLINICAL DASHBOARD (REAL-TIME PHYSIOLOGY MONITOR)</span>
</div>
      </header>

      <main className="kgen-grid">
        <section className="kgen-panel kgen-live-panel">
          <div className="kgen-panel-title-row">
  <h2>01. Live Physiology</h2>

  <span className="kgen-header-clock">
    <span className="kgen-clock-dot" />
    <span>Current time: {live.clockText || formatLiveClock()}</span>
  </span>
</div>

          <div className="kgen-live-content">
            <div className="kgen-wave-stack">
<WaveChart
  label="ECG"
  color={getLiveColor(live, "heartRate", live.alertColor || "red")}
  values={live.ecg}
  onOpen={() => setActiveWaveformId("ecg")}
  ariaLabel="Open ECG waveform popup"
/>

<WaveChart
  color={getLiveColor(live, "respiratoryRate", "yellow")}
  values={live.resp}
  compact
  onOpen={() => setActiveWaveformId("resp")}
  ariaLabel="Open respiratory waveform popup"
/>

<WaveChart
  label="PPG"
  color={getLiveColor(live, "spo2", "blue")}
  values={live.ppg}
  onOpen={() => setActiveWaveformId("ppg")}
  ariaLabel="Open PPG waveform popup"
/>

<WaveChart
  color={getLiveColor(live, "spo2", "blue")}
  values={live.ppgSoft}
  compact
  onOpen={() => setActiveWaveformId("ppgSoft")}
  ariaLabel="Open secondary PPG waveform popup"
/>

              <div className="kgen-time-axis">
                <span>0 mo</span>
                <span>2s</span>
                <span>4s</span>
                <span>6s</span>
                <span>12s</span>
                <span>16s</span>
              </div>
            </div>

            <aside className="kgen-side-vitals">
              <div className="kgen-side-vital">
                <span>Heart Rate</span>
                <strong>{live.heartRate}</strong>
              <MiniTrend
  color={getLiveColor(live, "heartRate", "red")}
  values={live.heartTrend}
  onOpen={() => setActiveWaveformId("heartTrend")}
  ariaLabel="Open heart rate trend popup"
/>
              </div>

              <div className="kgen-side-vital">
                <span>Respiratory Rate</span>
                <strong className="blue">{live.respiratoryRate}</strong>
         <MiniTrend
  color={getLiveColor(live, "respiratoryRate", "yellow")}
  values={live.respTrend}
  onOpen={() => setActiveWaveformId("respTrend")}
  ariaLabel="Open respiratory rate trend popup"
/>
              </div>

              <div className="kgen-side-vital">
                <span>SpO2</span>
                <strong className="blue">{live.spo2}%</strong>
                <MiniTrend
  color={getLiveColor(live, "spo2", "blue")}
  values={live.spo2Trend}
  onOpen={() => setActiveWaveformId("spo2Trend")}
  ariaLabel="Open SpO2 trend popup"
/>
              </div>
            </aside>
          </div>
        </section>

        <section className="kgen-panel kgen-labs-panel">
          <h2>03. Recent Lab Results &amp; Trends</h2>

          <div className="kgen-lab-grid">
           {labCards.map((item) => (
  <LabTile
    key={item.name}
    {...item}
    onOpenTrend={() => setActiveWaveformId(`lab-${item.name}`)}
  />
))}
          </div>

          <div className="kgen-mini-table">
            <span>06/23</span>
            <span>06/28</span>
            <span>07/07</span>
            <span>07/18</span>

            <b>125</b>
            <b>139</b>
            <b>141</b>
            <b>{live.glucose}</b>

            <b>{live.creatinine.toFixed(2)}</b>
            <b>14</b>
            <b>0.89</b>
            <b>{live.potassium.toFixed(1)}</b>
          </div>

          <button className="kgen-blue-btn" type="button" onClick={onOpenLabs}>
            Access full table
          </button>
        </section>

        <section className={`kgen-panel kgen-alert-panel ${alertColor}`}>
  <h2>02. Critical Alerts &amp; Interpretation</h2>

  <div className="kgen-alert-box">
    <div className="kgen-alert-icon">
      {alertColor === "blue" ? "✓" : "!"}
    </div>

    <h3>{interpretation.title}</h3>

    <p>
      <b>Rhythm:</b> {interpretation.rhythm}
    </p>

    <p>
      <b>PPG Signal:</b> {interpretation.ppg}
    </p>

    <p>
      <b>Likely Etiology:</b> {interpretation.likelyEtiology}
    </p>
  </div>
</section>

        <section className="kgen-panel kgen-labs-small-panel">
          <h2>03. Recent Lab Results &amp; Trends</h2>

          <div className="kgen-lab-grid small">
          {labCards.slice(0, 2).map((item) => (
  <LabTile
    key={item.name}
    {...item}
    onOpenTrend={() => setActiveWaveformId(`lab-${item.name}`)}
  />
))}
          </div>

          <button className="kgen-blue-btn" type="button" onClick={onOpenLabs}>
            Access full table
          </button>
        </section>

        <section className="kgen-panel kgen-vitals-panel">
          <h2>04. Vital Signs Log</h2>

          <table className="kgen-table vitals">
            <thead>
              <tr>
                <th>Parameter</th>
                <th>Value</th>
                <th>Unit</th>
                <th>Date</th>
              </tr>
            </thead>

            <tbody>
              {vitalRows.map((row) => (
                <tr key={row[0]}>
                  <td>{row[0]}</td>
                  <td>{row[1]}</td>
                  <td>{row[2]}</td>
                  <td>{row[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="kgen-panel kgen-med-panel">
          <h2>05. Medication Adherence</h2>

          <table className="kgen-table meds">
            <thead>
              <tr>
                <th>Med Name</th>
                <th>Dosage</th>
                <th>Not-Taken</th>
                <th>Date</th>
              </tr>
            </thead>

            <tbody>
             {(live.medicationRows?.length ? live.medicationRows : MEDICATION_ROWS).map((row, index) => (
                <tr key={`${row.sourceResource || "med"}-${row.id || row.med || row.name || "row"}-${row.date || row.prescribed || ""}-${index}`}>
                  <td>
                    <strong>{row.med}</strong>
                    {row.sub && <small>{row.sub}</small>}
                  </td>

                  <td>
                    {row.warning && <span className="kgen-warning">▲</span>} {row.dose}
                  </td>

                  <td>
                    {(row.taken || []).map((item, takenIndex) => (
  <div
    key={`${row.sourceResource || "med"}-${row.id || index}-taken-${item.time || "time"}-${takenIndex}`}
  >
    <span className={item.ok ? "kgen-ok" : "kgen-no"}>
      {item.ok ? "✓" : "×"}
    </span>{" "}
    {item.time}
  </div>
))}
                  </td>

                  <td>{row.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>

      <footer className="kgen-footer">
        <span>
          Supervisory Governance | Safety Checks | Compliance | Outcomes: Personalized Care,
          Real-time Decisions, Specialist Level Support
        </span>

        <strong>KardioGenics</strong>
      </footer>
      {waveformOverlay && (
  <WaveformOverlay
    config={waveformOverlay}
    onClose={() => setActiveWaveformId(null)}
  />
)}
    </section>
  );
}

