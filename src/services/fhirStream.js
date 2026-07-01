const DEFAULT_STREAM_URL = "http://127.0.0.1:8000/api/stream?provider=epic&debug=true";
let activeEventSource = null;

const DEBUG_SSE =
  import.meta.env.DEV &&
  import.meta.env.VITE_DEBUG_FHIR_STREAM === "true";

function buildStreamUrl({ provider, patientId }) {
  const baseUrl =
    import.meta.env.VITE_FHIR_STREAM_URL ||
    DEFAULT_STREAM_URL;

  const url = new URL(baseUrl, window.location.origin);

  const resolvedProvider =
    provider ||
    import.meta.env.VITE_FHIR_PROVIDER ||
    url.searchParams.get("provider") ||
    "epic";

  url.searchParams.set("provider", resolvedProvider);

  if (patientId) {
    url.searchParams.set("patient_id", patientId);
  } else {
    url.searchParams.delete("patient_id");
  }

  if (!url.searchParams.has("debug")) {
    url.searchParams.set("debug", "true");
  }

  return url.toString();
}

export function connectFhirStream({
  provider,
  patientId,
  onFrame,
  onHeartbeat,
  onError,
}) {
  const streamUrl = buildStreamUrl({ provider, patientId });

  if (DEBUG_SSE) {
    console.log("[KGEN SSE CONNECT]", {
      streamUrl,
      provider,
      patientId,
    });
  }

  if (activeEventSource) {
    activeEventSource.close();
    activeEventSource = null;
  }

  const eventSource = new EventSource(streamUrl, {
    withCredentials: true,
  });

  activeEventSource = eventSource;

  eventSource.addEventListener("fhir-frame", (event) => {
    try {
      const frame = JSON.parse(event.data);

      if (DEBUG_SSE) {
        console.log("[KGEN SSE FRAME]", {
          source: frame.source,
          status: frame.status,
          receivedAt: frame.receivedAt,
          fhirFields: frame.dataQuality?.fhirFields,
          fallbackFields: frame.dataQuality?.fallbackFields,
          observationCount: frame.dataQuality?.observationCount,
          matchedObservationCount: frame.dataQuality?.matchedObservationCount,
          vitals: frame.vitals,
          labs: frame.labs,
        });
      }

      onFrame?.(frame);
    } catch (error) {
      console.error("[KGEN SSE FRAME ERROR]", error);
      onError?.(error);
    }
  });

  eventSource.addEventListener("heartbeat", (event) => {
    try {
      const heartbeat = JSON.parse(event.data);

      if (DEBUG_SSE) {
        console.log("[KGEN SSE HEARTBEAT]", heartbeat);
      }

      onHeartbeat?.(heartbeat);
    } catch {
      const heartbeat = { status: "heartbeat" };

      if (DEBUG_SSE) {
        console.log("[KGEN SSE HEARTBEAT]", heartbeat);
      }

      onHeartbeat?.(heartbeat);
    }
  });

  eventSource.onerror = (error) => {
    console.error("[KGEN SSE ERROR]", error);
    onError?.(error);
  };

  return () => {
    if (DEBUG_SSE) {
      console.log("[KGEN SSE CLOSE]");
    }

    if (activeEventSource === eventSource) {
      activeEventSource = null;
    }

    eventSource.close();
  };
}