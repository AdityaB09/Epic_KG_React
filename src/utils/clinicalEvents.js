export function formatCurrentTime() {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true
  }).format(new Date());
}

export function getVitalAlerts(telemetry) {
  if (!telemetry) return [];

  const alerts = [];

  if (telemetry.heartRate >= 125) {
    alerts.push({
      id: "critical-hr",
      level: "critical",
      title: "Critical heart rate",
      message: `Heart rate is ${telemetry.heartRate} bpm.`
    });
  } else if (telemetry.heartRate >= 105) {
    alerts.push({
      id: "warning-hr",
      level: "warning",
      title: "Elevated heart rate",
      message: `Heart rate is ${telemetry.heartRate} bpm.`
    });
  }

  if (telemetry.oxygen <= 90) {
    alerts.push({
      id: "critical-spo2",
      level: "critical",
      title: "Oxygen drop",
      message: `SpO₂ dropped to ${telemetry.oxygen}%.`
    });
  } else if (telemetry.oxygen <= 94) {
    alerts.push({
      id: "warning-spo2",
      level: "warning",
      title: "Low oxygen",
      message: `SpO₂ is ${telemetry.oxygen}%.`
    });
  }

  if (telemetry.systolic >= 145 || telemetry.diastolic >= 95) {
    alerts.push({
      id: "warning-bp",
      level: "warning",
      title: "High blood pressure",
      message: `BP is ${telemetry.systolic}/${telemetry.diastolic}.`
    });
  }

  if (telemetry.respiratoryRate >= 26) {
    alerts.push({
      id: "warning-rr",
      level: "warning",
      title: "High respiratory rate",
      message: `Respiratory rate is ${telemetry.respiratoryRate}/min.`
    });
  }

  if (telemetry.temperature >= 100.4) {
    alerts.push({
      id: "warning-temp",
      level: "warning",
      title: "Fever detected",
      message: `Temperature is ${telemetry.temperature}°F.`
    });
  }

  if (telemetry.rhythm !== "normal") {
    alerts.push({
      id: `rhythm-${telemetry.rhythm}`,
      level: telemetry.rhythm === "arrhythmia" ? "critical" : "warning",
      title: "Rhythm change",
      message: telemetry.alert
    });
  }

  return alerts;
}