export const patients = [
  {
    id: "p-001",
    name: "Leslie Abbott",
    age: 48,
    sex: "Female",
    mrn: "87675858",
    unit: "CTU",
    location: "Bed 12A",
    allergies: "Penicillin",
    status: "Code-Status",
    risk: "Stable",
    avatar: "LA",
    lastSeen: "2 min ago"
  },
  {
    id: "p-002",
    name: "Hector Adams",
    age: 48,
    sex: "Male",
    mrn: "87675859",
    unit: "CTU",
    location: "Bed 08B",
    allergies: "None",
    status: "Review",
    risk: "Watch",
    avatar: "HA",
    lastSeen: "8 min ago"
  },
  {
    id: "p-003",
    name: "Blake Alexander",
    age: 48,
    sex: "Male",
    mrn: "87675860",
    unit: "CTU",
    location: "Bed 04C",
    allergies: "Latex",
    status: "Code-Status",
    risk: "Stable",
    avatar: "BA",
    lastSeen: "15 min ago"
  },
  {
    id: "p-004",
    name: "Angela Beaver",
    age: 48,
    sex: "Female",
    mrn: "87675861",
    unit: "CONSULTS",
    location: "Room 214",
    allergies: "Aspirin",
    status: "Follow-up",
    risk: "Watch",
    avatar: "AB",
    lastSeen: "1 hr ago"
  },
  {
    id: "p-005",
    name: "Yvette Blanchard",
    age: 48,
    sex: "Female",
    mrn: "87675862",
    unit: "CONSULTS",
    location: "Room 317",
    allergies: "None",
    status: "Code-Status",
    risk: "Stable",
    avatar: "YB",
    lastSeen: "Today"
  },
  {
    id: "p-006",
    name: "Lawrence Brooks",
    age: 48,
    sex: "Male",
    mrn: "87675863",
    unit: "CONSULTS",
    location: "Room 401",
    allergies: "Peanuts",
    status: "Urgent",
    risk: "High",
    avatar: "LB",
    lastSeen: "Today"
  },
  {
    id: "p-007",
    name: "Jeffrey Clark",
    age: 48,
    sex: "Male",
    mrn: "87675864",
    unit: "CONSULTS",
    location: "Room 118",
    allergies: "None",
    status: "Discharge",
    risk: "Stable",
    avatar: "JC",
    lastSeen: "Yesterday"
  },
  {
    id: "p-008",
    name: "Kathryn Cooper",
    age: 48,
    sex: "Female",
    mrn: "87675865",
    unit: "CONSULTS",
    location: "Room 205",
    allergies: "Sulfa",
    status: "Code-Status",
    risk: "Watch",
    avatar: "KC",
    lastSeen: "Yesterday"
  }
];

export const medications = [
  { id: "m1", medication: "Ibuprofen 200mg", dose: "1 tablet", frequency: "Daily", prescribed: "01-01-2022", status: "Current" },
  { id: "m2", medication: "Warfarin 1mg", dose: "2 pills", frequency: "Daily", prescribed: "01-03-2022", status: "Current" },
  { id: "m3", medication: "Atorvastatin 20mg", dose: "1 tablet", frequency: "Nightly", prescribed: "01-08-2022", status: "Current" },
  { id: "m4", medication: "Metformin 500mg", dose: "1 tablet", frequency: "Twice daily", prescribed: "01-12-2022", status: "Paused" }
];

export const labs = [
  { id: "l1", title: "X-Ray", description: "Chest imaging report available for review.", value: "Ready", reference: "Radiology", date: "Today" },
  { id: "l2", title: "CBT", description: "Complete blood test with abnormality flags.", value: "12.8", reference: "11-16", date: "Today" },
  { id: "l3", title: "Glucose", description: "Fasting glucose reading.", value: "96 mg/dL", reference: "70-99", date: "Yesterday" },
  { id: "l4", title: "Creatinine", description: "Kidney function marker.", value: "0.9 mg/dL", reference: "0.6-1.2", date: "Yesterday" },
  { id: "l5", title: "Sodium", description: "Electrolyte panel reading.", value: "139 mmol/L", reference: "135-145", date: "2 days ago" }
];

export const documents = [
  { id: "d1", title: "Consent Form", type: "PDF", owner: "Nursing", date: "Today" },
  { id: "d2", title: "Discharge Summary", type: "DOC", owner: "Resident Team", date: "Yesterday" },
  { id: "d3", title: "Insurance Card", type: "Image", owner: "Front Desk", date: "Last week" }
];

export const recentSearches = [
  { type: "Patient", title: "Calvin Hawkins", meta: "MRN: 87675309" },
  { type: "Patient", title: "Lisa Thompson", meta: "MRN: 87675300" },
  { type: "Medication", title: "Ibuprofen 200mg", meta: "1 pill, Daily" },
  { type: "Lab Report", title: "X-Ray", meta: "Report ready" },
  { type: "Document", title: "Lorem", meta: "Document note" }
];
