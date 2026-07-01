const MAX_POINTS = 180;

function classifyTelemetry(data) {

  if (data.heartRate <= 55) {
    return {
      rhythm: "bradycardia",
      alert: "Low heart rate detected"
    };
  }

  if (data.heartRate >= 105 && data.heartRate < 125) {
    return {
      rhythm: "tachycardia",
      alert: "Elevated heart rate"
    };
  }

  if (
    data.oxygen <= 90 ||
    data.heartRate >= 125
  ) {
    return {
      rhythm: "arrhythmia",
      alert: "Irregular rhythm detected"
    };
  }

  return {
    rhythm: "normal",
    alert: "Normal sinus rhythm"
  };
}

function rhythmValue(t, rhythm) {
  const beat = t % 1;
  let value = 0.5;

  if (rhythm === "flatline") {
    return 0.5 + Math.random() * 0.01;
  }

  if (beat < 0.08) value = 0.5;
  else if (beat < 0.12) value = 0.58;
  else if (beat < 0.16) value = 0.95;
  else if (beat < 0.2) value = 0.18;
  else if (beat < 0.28) value = 0.62;
  else if (beat < 0.45) value = 0.52;

  if (rhythm === "tachycardia") {
    value += Math.sin(t * 35) * 0.02;
  }

  if (rhythm === "bradycardia") {
    value = value * 0.9;
  }

  if (rhythm === "arrhythmia") {

  if (Math.random() > 0.82) {
    value += (Math.random() - 0.5) * 0.9;
  }

  if (Math.random() > 0.93) {
    value = Math.random() > 0.5 ? 0.98 : 0.08;
  }

  value += Math.sin(t * 18) * 0.12;
}

  return Math.max(0.08, Math.min(0.95, value));
}

export function createInitialTelemetry(patientId, risk = "Stable") {
  const base =
    risk === "High"
      ? {
          heartRate: 118,
          oxygen: 91,
          systolic: 148,
          diastolic: 92,
          respiratoryRate: 24,
          temperature: 100.8
        }
      : risk === "Watch"
      ? {
          heartRate: 104,
          oxygen: 95,
          systolic: 132,
          diastolic: 84,
          respiratoryRate: 20,
          temperature: 99.1
        }
      : {
          heartRate: 78,
          oxygen: 98,
          systolic: 122,
          diastolic: 78,
          respiratoryRate: 16,
          temperature: 98.6
        };

  const classification = classifyTelemetry(base);

  return {
    patientId,
    ...base,
    ...classification,
    ecg: Array.from({ length: MAX_POINTS }, (_, index) => ({
      x: index,
      y: 0.5
    }))
  };
}

export function nextTelemetryFrame(prev) {
  const heartNoise = Math.round((Math.random() - 0.48) * 6);
  const oxygenNoise = Math.random() > 0.88 ? Math.round((Math.random() - 0.5) * 3) : 0;

  const updatedVitals = {
    ...prev,
    heartRate: Math.max(42, Math.min(145, prev.heartRate + heartNoise)),
    oxygen: Math.max(86, Math.min(100, prev.oxygen + oxygenNoise)),
    systolic: Math.max(90, Math.min(170, prev.systolic + Math.round((Math.random() - 0.5) * 3))),
    diastolic: Math.max(55, Math.min(110, prev.diastolic + Math.round((Math.random() - 0.5) * 2))),
    respiratoryRate: Math.max(8, Math.min(32, prev.respiratoryRate + Math.round((Math.random() - 0.5) * 2)))
  };

  const classification = classifyTelemetry(updatedVitals);

  const speed =
    classification.rhythm === "tachycardia"
      ? 0.09
      : classification.rhythm === "bradycardia"
      ? 0.035
      : classification.rhythm === "arrhythmia"
      ? 0.07
      : 0.055;

  const nextIndex = prev.ecg[prev.ecg.length - 1].x + 1;
  const t = Date.now() / 1000 * speed + nextIndex * 0.025;
  const y = rhythmValue(t, classification.rhythm);

  return {
    ...updatedVitals,
    ...classification,
    ecg: [...prev.ecg.slice(1), { x: nextIndex, y }]
  };
}