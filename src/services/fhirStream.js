const DEFAULT_STREAM_URL = "http://127.0.0.1:8000/api/stream?debug=true";
let activeEventSource = null;

const DEBUG_SSE =
  import.meta.env.DEV &&
  import.meta.env.VITE_DEBUG_FHIR_STREAM === "true";


function buildStreamUrl() {
  const baseUrl =
    import.meta.env.VITE_FHIR_STREAM_URL ||
    "http://127.0.0.1:8000/api/stream?debug=true";

  const url = new URL(baseUrl);

  // Force Oracle stream. Do not let old Firely params survive.
  url.searchParams.delete("provider");
  url.searchParams.delete("patient_id");
  url.searchParams.set("debug", "true");

  return url.toString();
}



export function connectFhirStream({
  provider,
  patientId,
  onFrame,
  onHeartbeat,
  onError,
}) {
  const streamUrl = buildStreamUrl({
    provider: "oracle",
    patientId: "",
  });

  if (DEBUG_SSE) {
  console.log("[KGEN SSE CONNECT]", {
    streamUrl,
    provider: "oracle",
    patientId: ""
  });
}
  
if (activeEventSource) {
  activeEventSource.close();
  activeEventSource = null;
}
 

  const eventSource = new EventSource(streamUrl, {
    withCredentials: true,
  });

  let lastOracleHash = null;

  activeEventSource = eventSource;

  function tinyHash(value) {
    const text = JSON.stringify(value ?? {});
    let hash = 0;

    for (let i = 0; i < text.length; i += 1) {
      hash = (hash << 5) - hash + text.charCodeAt(i);
      hash |= 0;
    }

    return String(hash);
  }

  function handleFrame(event) {
    try {
      const frame = JSON.parse(event.data);

      const oracleValues =
        frame.debug?.rawExtractedFhirValues || {
          vitals: frame.vitals,
          labs: frame.labs,
        };

      const oracleHash = tinyHash(oracleValues);
      const oracleChanged = oracleHash !== lastOracleHash;
      lastOracleHash = oracleHash;
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
        oracleHash,
        oracleChanged
      });
    }

      onFrame?.(frame);
    } catch (error) {
      console.error("[KGEN SSE FRAME ERROR]", error);
      onError?.(error);
    }
  }

  eventSource.addEventListener("fhir-frame", handleFrame);

  eventSource.addEventListener("heartbeat", (event) => {
    try {
      const heartbeat = JSON.parse(event.data);
    if (DEBUG_SSE) {
      console.log("[KGEN SSE HEARTBEAT]", heartbeat);
      onHeartbeat?.(heartbeat);
    }
    } catch {
      if (DEBUG_SSE) {
      console.log("[KGEN SSE HEARTBEAT]", { status: "heartbeat" });
      onHeartbeat?.({ status: "heartbeat" });
      }
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