import { useEffect, useMemo, useRef, useState } from "react";
import { patients as mockPatients, medications as mockMedications, labs as mockLabs, documents as mockDocuments, recentSearches } from "./data/mockData";
import { fetchFirelyPatientClinicalData, fetchFirelyPatients, testFirelyConnection } from "./services/fhirService";

import Navbar from "./components/Navbar";
import PatientSidebar from "./components/PatientSidebar";
import PatientSummary from "./components/PatientSummary";
import ECGPanel from "./components/ECGPanel";
import WidgetCard from "./components/WidgetCard";
import OverlayModal from "./components/OverlayModal";
import SearchOverlay from "./components/SearchOverlay";
import AlertPanel from "./components/AlertPanel";
import TimelineFeed from "./components/TimelineFeed";
import MultiPatientMonitor from "./components/MultiPatientMonitor";
import ClinicalPhysiologyPage from "./components/ClinicalPhysiologyPage";


import "./index.css";

import { createInitialTelemetry, nextTelemetryFrame } from "./services/telemetryService";
import { formatCurrentTime, getVitalAlerts } from "./utils/clinicalEvents";

export default function App() {
  const [patients, setPatients] = useState(mockPatients);
  const [medications, setMedications] = useState(mockMedications);
  const [labs, setLabs] = useState(mockLabs);
  const [documents, setDocuments] = useState(mockDocuments);
  const [fhirEnabled, setFhirEnabled] = useState(false);
  const [fhirStatus, setFhirStatus] = useState("Using mock data");
  const [fhirLoading, setFhirLoading] = useState(false);

  const [selectedPatientId, setSelectedPatientId] = useState(mockPatients[0].id);
  const [modal, setModal] = useState(null);
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false);
  const [compactMode, setCompactMode] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [globalSearchQuery, setGlobalSearchQuery] = useState("");
  const [darkMode, setDarkMode] = useState(false);
  const [timelineEvents, setTimelineEvents] = useState([]);

  const searchRef = useRef(null);
  const lastAlertSignatureRef = useRef("");
  const [multiMonitorOpen, setMultiMonitorOpen] = useState(false);
  
  const [activePage, setActivePage] = useState("physiology"); // "dashboard", "monitor", "physiology" 
  const [monitorPatientIds, setMonitorPatientIds] = useState([]);
  
  const [monitorSlots, setMonitorSlots] = useState([null, null, null, null]);

  const [telemetryMap, setTelemetryMap] = useState(() =>
    Object.fromEntries(
      mockPatients.map((patient) => [
        patient.id,
        createInitialTelemetry(patient.id, patient.risk)
      ])
    )
  );

  useEffect(() => {
    setTelemetryMap((prev) => {
      const next = { ...prev };

      for (const patient of patients) {
        if (!next[patient.id]) {
          next[patient.id] = createInitialTelemetry(patient.id, patient.risk);
        }
      }

      return next;
    });
  }, [patients]);

  useEffect(() => {
    const interval = setInterval(() => {
      setTelemetryMap((prev) => {
        const updated = {};

        for (const patient of patients) {
          updated[patient.id] = nextTelemetryFrame(prev[patient.id] ?? createInitialTelemetry(patient.id, patient.risk));
        }

        return updated;
      });
    }, 90);

    return () => clearInterval(interval);
  }, [patients]);

  const selectedPatient = useMemo(
    () => patients.find((patient) => patient.id === selectedPatientId) ?? patients[0],
    [selectedPatientId]
  );

  const selectedTelemetry = telemetryMap[selectedPatientId];

  const activeAlerts = useMemo(
    () => getVitalAlerts(selectedTelemetry),
    [selectedTelemetry]
  );

  useEffect(() => {
    if (!selectedTelemetry) return;

    const signature = activeAlerts.map((alert) => alert.id).join("|");

    if (!signature || signature === lastAlertSignatureRef.current) return;

    lastAlertSignatureRef.current = signature;

    const newEvents = activeAlerts.map((alert) => ({
      id: `${Date.now()}-${alert.id}`,
      patientId: selectedPatientId,
      time: formatCurrentTime(),
      type: alert.level === "critical" ? "Critical Alert" : "Alert",
      level: alert.level,
      title: alert.title,
      message: alert.message
    }));

    setTimelineEvents((prev) => [...newEvents, ...prev].slice(0, 20));
  }, [activeAlerts, selectedTelemetry, selectedPatientId]);

  useEffect(() => {
    setTimelineEvents([
      {
        id: `selected-${Date.now()}`,
        patientId: selectedPatientId,
        time: formatCurrentTime(),
        type: "Patient Selected",
        level: "normal",
        title: `${selectedPatient.name} opened`,
        message: `Live vitals monitoring started for MRN ${selectedPatient.mrn}.`
      }
    ]);

    lastAlertSignatureRef.current = "";
  }, [selectedPatientId]);

  useEffect(() => {
    function handleOutsideClick(event) {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setGlobalSearchOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, []);

  useEffect(() => {
    document.body.classList.toggle("dark-mode", darkMode);
  }, [darkMode]);

  const handleSelectPatient = (id) => {
    setSelectedPatientId(id);
    setModal(null);
    setGlobalSearchOpen(false);
    setGlobalSearchQuery("");
  };


  async function loadFirelySandbox() {
    setFhirLoading(true);
    setFhirStatus("Connecting to Firely sandbox...");

    try {
      const metadata = await testFirelyConnection();
      const firelyPatients = await fetchFirelyPatients(8);

      if (!firelyPatients.length) {
        throw new Error("No Patient resources returned from Firely sandbox.");
      }

      setPatients(firelyPatients);
      setSelectedPatientId(firelyPatients[0].id);
      setFhirEnabled(true);
      setFhirStatus(`Connected: ${metadata.software} ${metadata.version}`);
    } catch (error) {
      console.error(error);
      setFhirStatus("Firely sandbox could not be loaded. Mock data is still active.");
      setFhirEnabled(false);
    } finally {
      setFhirLoading(false);
    }
  }

  function useMockData() {
    setPatients(mockPatients);
    setMedications(mockMedications);
    setLabs(mockLabs);
    setDocuments(mockDocuments);
    setSelectedPatientId(mockPatients[0].id);
    setFhirEnabled(false);
    setFhirStatus("Using mock data");
  }

  useEffect(() => {
    let ignore = false;

    async function loadClinicalData() {
      if (!fhirEnabled) {
        setMedications(mockMedications);
        setLabs(mockLabs);
        setDocuments(mockDocuments);
        return;
      }

      try {
        const data = await fetchFirelyPatientClinicalData(selectedPatientId);
        if (ignore) return;

        setMedications(data.medications.length ? data.medications : mockMedications);
        setLabs(data.observations.length ? data.observations : mockLabs);
        setDocuments(data.documents.length ? data.documents : mockDocuments);
      } catch (error) {
        console.error(error);
        if (!ignore) {
          setMedications(mockMedications);
          setLabs(mockLabs);
          setDocuments(mockDocuments);
        }
      }
    }

    loadClinicalData();

    return () => {
      ignore = true;
    };
  }, [fhirEnabled, selectedPatientId]);

  const openModal = (type) => setModal(type);
  const closeModal = () => setModal(null);

  function renderDashboardPage() {
  return (
    <>
      <div className="main-toolbar">
        <div>
          <p className="eyebrow">Clinical dashboard</p>
          <h1>{selectedPatient.name}</h1>
        </div>

        <div className="toolbar-actions">
          <button className="ghost-btn" onClick={() => setDarkMode((value) => !value)}>
            {darkMode ? "Light mode" : "Dark mode"}
          </button>

          <button className="ghost-btn" onClick={() => setCompactMode((value) => !value)}>
            {compactMode ? "Comfort view" : "Compact view"}
          </button>

          <button className="primary-btn" onClick={() => openModal("note")}>
            + Add note
          </button>

          <button className="ghost-btn" onClick={loadFirelySandbox} disabled={fhirLoading}>
            {fhirLoading ? "Loading Firely..." : "Use Firely"}
          </button>

          <button className="ghost-btn" onClick={useMockData}>
            Use mock
          </button>
        </div>
      </div>

      <section className="fhir-status-card">
        <strong>{fhirEnabled ? "Firely sandbox mode" : "Mock testing mode"}</strong>
        <p>
          {fhirStatus}. Live ECG and vitals are still simulated because public FHIR
          sandboxes do not stream bedside telemetry.
        </p>
      </section>

      <AlertPanel alerts={activeAlerts} />

      <section className="dashboard-grid priority-two-grid">
        <div className="patient-column">
          <PatientSummary patient={selectedPatient} />
          <ECGPanel telemetry={selectedTelemetry} />
        </div>

        <TimelineFeed events={timelineEvents} />
      </section>

      <section className={`widgets-grid ${compactMode ? "compact" : ""}`}>
        <WidgetCard
          title="Medication Log"
          items={medications}
          kind="medications"
          onAdd={() => openModal("medications")}
          onSeeAll={() => openModal("medications")}
          defaultExpanded={false}
          resetKey={selectedPatientId}
        />

        <WidgetCard
          title="Lab Results"
          items={labs}
          kind="labs"
          onAdd={() => openModal("labs")}
          onSeeAll={() => openModal("labs")}
          defaultExpanded={false}
          resetKey={selectedPatientId}
        />
      </section>

      <WidgetCard
        title="Documents"
        items={documents}
        kind="documents"
        onAdd={() => openModal("documents")}
        onSeeAll={() => openModal("documents")}
        variant="toggled"
        fullWidth
        defaultExpanded={false}
        resetKey={selectedPatientId}
      />
    </>
  );
}

function renderMonitorPage() {
  return (
    <MultiPatientMonitor
      patients={patients}
      telemetryMap={telemetryMap}
      monitorSlots={monitorSlots}
      onDropPatient={(slotIndex, patientId) => {
        setMonitorSlots((prev) => {
          const next = [...prev];

          const existingIndex = next.indexOf(patientId);
          if (existingIndex !== -1) {
            next[existingIndex] = null;
          }

          next[slotIndex] = patientId;
          return next;
        });
      }}
      onRemovePatient={(slotIndex) => {
        setMonitorSlots((prev) => {
          const next = [...prev];
          next[slotIndex] = null;
          return next;
        });
      }}
    />
  );
}

function renderPhysiologyPage() {
  return (
    <ClinicalPhysiologyPage
      patient={selectedPatient}
      onOpenLabs={() => openModal("labs")}
    />
  );
}
function renderActivePage() {
  if (activePage === "dashboard") return renderDashboardPage();
  if (activePage === "monitor") return renderMonitorPage();
  if (activePage === "physiology") return renderPhysiologyPage();

  return renderPhysiologyPage();
}

  return (
    <div className={`app-shell ${compactMode ? "compact-mode" : "comfort-mode"}`}>
      <div ref={searchRef}>
        <Navbar
  searchValue={globalSearchQuery}
  alertCount={activeAlerts.length}
  activePage={activePage}
  onPageChange={setActivePage}
  onSearchChange={(value) => {
    setGlobalSearchQuery(value);
    setGlobalSearchOpen(true);
  }}
  onSearchFocus={() => setGlobalSearchOpen(true)}
  onToggleSidebar={() => setSidebarCollapsed((value) => !value)}
/>

        {globalSearchOpen && (
          <SearchOverlay
            patients={patients}
            recentSearches={recentSearches}
            query={globalSearchQuery}
            onClose={() => setGlobalSearchOpen(false)}
            onSelectPatient={handleSelectPatient}
          />
        )}
      </div>

      <div className={`workspace ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
        <PatientSidebar
          patients={patients}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handleSelectPatient}
          onAddPatient={() => openModal("patient")}
          collapsed={sidebarCollapsed}
        />

        <main className="dashboard-main" aria-label="Patient dashboard">
          {/* <div className="main-toolbar">
            <div>
              <p className="eyebrow">Clinical dashboard</p>
              <h1>{selectedPatient.name}</h1>
            </div>

            <div className="toolbar-actions">
              
              <button className="ghost-btn" onClick={() => setDarkMode((value) => !value)}>
                {darkMode ? "Light mode" : "Dark mode"}
              </button>

              <button className="ghost-btn" onClick={() => setCompactMode((value) => !value)}>
                {compactMode ? "Comfort view" : "Compact view"}
              </button>

              <button className="primary-btn" onClick={() => openModal("note")}>
                + Add note
              </button>
            </div>
          </div>

          <AlertPanel alerts={activeAlerts} />


          <section className="dashboard-grid priority-two-grid">
            <div className="patient-column">
              
              <PatientSummary patient={selectedPatient} />
              <ECGPanel telemetry={selectedTelemetry} />
            </div>

            <TimelineFeed events={timelineEvents} />
          </section> */}
          {renderActivePage()}
        </main>
      </div>

      {modal && (
        <OverlayModal
          type={modal}
          patient={selectedPatient}
          medications={medications}
          labs={labs}
          documents={documents}
          onClose={closeModal}
        />
      )}
    </div>
  );
}