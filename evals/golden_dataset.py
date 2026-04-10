"""
Golden evaluation dataset.

Provides:
  CORPUS   — small, self-contained text chunks (one per entry) that are
             seeded into dedicated eval OpenSearch indices.  No S3 or real
             PDFs required — ideal for CI.

  SAMPLES  — 12 Q&A pairs (3 per medical domain) used to evaluate the RAG
             pipeline.  Every sample carries:
               domain             : one of the four medical document domains
               question           : the user query
               reference          : the expected ideal answer (ground truth)
               reference_contexts : the corpus chunks that contain the answer
               corpus_filename    : filename written to OpenSearch metadata

Design notes
------------
* reference_contexts ARE the corpus chunks (verbatim).  This ensures that a
  correctly configured BM25 retriever can always score ≥ 1.0 context recall —
  any degradation below threshold signals a regression in search quality.
* Questions are keyword-rich so BM25 can surface the right chunk without
  needing a real embedding model (random / zero vectors work in CI).
* Three cognitive levels per domain: factual recall, mechanism / process,
  and clinical application.
"""
from __future__ import annotations

# ─── Corpus ──────────────────────────────────────────────────────────────────
# Each entry maps to ONE chunk stored in OpenSearch.  The "domain" key is used
# to route the chunk to the correct eval index.

CORPUS: list[dict] = [

    # ── Disease Study ─────────────────────────────────────────────────────────
    {
        "domain": "disease_study",
        "filename": "diabetes_overview.txt",
        "corpus_id": "ds-001",
        "text": (
            "Type 2 diabetes mellitus is a chronic metabolic disorder characterised by "
            "insulin resistance and relative insulin deficiency. "
            "Primary symptoms include polydipsia (excessive thirst), polyuria (frequent urination), "
            "polyphagia (increased appetite), unexplained weight loss, fatigue, blurred vision, "
            "and slow-healing wounds. "
            "Diagnosis is confirmed by fasting plasma glucose ≥ 126 mg/dL or HbA1c ≥ 6.5 %. "
            "First-line pharmacotherapy is metformin combined with structured lifestyle modification."
        ),
    },
    {
        "domain": "disease_study",
        "filename": "hypertension_guide.txt",
        "corpus_id": "ds-002",
        "text": (
            "Hypertension (high blood pressure) is defined as sustained systolic BP ≥ 130 mmHg "
            "or diastolic BP ≥ 80 mmHg. "
            "It is a major risk factor for stroke, myocardial infarction, heart failure, and "
            "chronic kidney disease. "
            "Non-pharmacological interventions include dietary sodium restriction below 2.3 g/day, "
            "regular aerobic exercise, weight reduction, and smoking cessation. "
            "First-line drug classes are ACE inhibitors, ARBs, calcium-channel blockers, and "
            "thiazide-type diuretics."
        ),
    },
    {
        "domain": "disease_study",
        "filename": "pneumonia_clinical_trial.txt",
        "corpus_id": "ds-003",
        "text": (
            "Community-acquired pneumonia (CAP) is an acute infection of the pulmonary parenchyma "
            "acquired outside a healthcare setting. "
            "The most common causative organism in adults is Streptococcus pneumoniae, followed by "
            "Haemophilus influenzae and atypical organisms such as Mycoplasma pneumoniae. "
            "Clinical features include fever, productive cough, dyspnoea, pleuritic chest pain, "
            "and consolidation on chest X-ray. "
            "Severity is stratified using the CURB-65 score; scores ≥ 2 warrant hospital admission. "
            "Standard empirical treatment for non-severe CAP is amoxicillin 500 mg TDS for 5 days."
        ),
    },

    # ── Medicine Study ────────────────────────────────────────────────────────
    {
        "domain": "medicine_study",
        "filename": "aspirin_pharmacology.txt",
        "corpus_id": "ms-001",
        "text": (
            "Aspirin (acetylsalicylic acid) is a non-selective, irreversible inhibitor of "
            "cyclooxygenase-1 (COX-1) and COX-2 enzymes. "
            "Pharmacological effects include analgesia, antipyresis, anti-inflammation at higher doses, "
            "and platelet aggregation inhibition at low doses (75–100 mg/day). "
            "Low-dose aspirin is used for secondary prevention of myocardial infarction and ischaemic "
            "stroke in high-risk patients. "
            "Common adverse effects are gastrointestinal bleeding, peptic ulcer, and aspirin-exacerbated "
            "respiratory disease. "
            "Aspirin is contraindicated in children under 12 due to the risk of Reye syndrome."
        ),
    },
    {
        "domain": "medicine_study",
        "filename": "metformin_monograph.txt",
        "corpus_id": "ms-002",
        "text": (
            "Metformin (biguanide class) is the preferred first-line oral hypoglycaemic agent for "
            "type 2 diabetes. "
            "Its primary mechanism is suppression of hepatic gluconeogenesis via activation of "
            "AMP-activated protein kinase (AMPK). "
            "It also improves peripheral insulin sensitivity and reduces intestinal glucose absorption. "
            "Standard adult dosing starts at 500 mg twice daily with meals, titrated to a maximum of "
            "2550 mg/day. "
            "Key adverse effects include GI upset, lactic acidosis (rare, contraindicated in eGFR < 30), "
            "and vitamin B12 deficiency with long-term use. "
            "Metformin does not cause hypoglycaemia when used as monotherapy."
        ),
    },
    {
        "domain": "medicine_study",
        "filename": "penicillin_monograph.txt",
        "corpus_id": "ms-003",
        "text": (
            "Penicillin G and penicillin V are beta-lactam antibiotics that inhibit bacterial cell-wall "
            "synthesis by irreversibly binding penicillin-binding proteins (PBPs). "
            "They are the drugs of choice for streptococcal infections, including group A streptococcal "
            "pharyngitis and syphilis. "
            "Penicillin V is the oral formulation with a typical adult dose of 250–500 mg every 6 hours "
            "for 10 days for streptococcal throat infection. "
            "The most common adverse reaction is allergic hypersensitivity (rash, urticaria, anaphylaxis "
            "in 0.01–0.05 % of patients). "
            "Cross-reactivity with cephalosporins occurs in approximately 1–2 % of penicillin-allergic patients."
        ),
    },

    # ── Medicine Expiry ───────────────────────────────────────────────────────
    {
        "domain": "medicine_expiry",
        "filename": "amoxicillin_stability.txt",
        "corpus_id": "me-001",
        "text": (
            "Amoxicillin capsules and tablets should be stored at 20–25 °C (68–77 °F) in a tightly "
            "sealed container, protected from moisture and light. "
            "The shelf life from the manufacturer is 2–3 years from the date of manufacture. "
            "Reconstituted oral suspension must be refrigerated at 2–8 °C and discarded after 14 days. "
            "Chemical degradation accelerates above 30 °C; potency can fall below 90 % within 3 months "
            "when stored at 40 °C. "
            "Expired amoxicillin should be disposed of via a pharmacy take-back programme in accordance "
            "with local pharmaceutical waste regulations."
        ),
    },
    {
        "domain": "medicine_expiry",
        "filename": "insulin_cold_chain.txt",
        "corpus_id": "me-002",
        "text": (
            "Unopened insulin vials and pens must be refrigerated between 2 °C and 8 °C. "
            "Insulin must never be frozen; freezing causes protein denaturation and renders it ineffective. "
            "Once opened (in use), insulin vials and cartridges can be kept at room temperature "
            "(below 30 °C) for up to 28 days. "
            "Insulin exposed to temperatures above 37 °C for more than 24 hours should be discarded. "
            "Direct sunlight must be avoided as UV radiation accelerates insulin degradation. "
            "Cold-chain documentation must accompany all insulin shipments per WHO/PIC/S guidelines."
        ),
    },
    {
        "domain": "medicine_expiry",
        "filename": "vaccine_cold_chain.txt",
        "corpus_id": "me-003",
        "text": (
            "Most live attenuated vaccines (MMR, varicella, yellow fever) require storage at −15 °C "
            "to −25 °C to maintain potency. "
            "Inactivated vaccines (influenza, hepatitis A/B, IPV) require 2–8 °C and must not be frozen. "
            "Exposure to temperatures outside the recommended range can reduce immunogenicity without "
            "changing the appearance of the vaccine. "
            "The Vaccine Vial Monitor (VVM) heat indicator must be checked before administration; "
            "a VVM that has reached discard point (inner square equals or is darker than the outer ring) "
            "means the vaccine should not be used. "
            "Cold-chain breaches must be reported within 24 hours to the pharmacy cold-chain supervisor."
        ),
    },

    # ── Equipment Study ───────────────────────────────────────────────────────
    {
        "domain": "equipment_study",
        "filename": "stethoscope_maintenance.txt",
        "corpus_id": "eq-001",
        "text": (
            "A stethoscope is an acoustic medical device used for auscultation of the heart, lungs, "
            "intestines, and blood vessels. "
            "It consists of a chest piece (diaphragm and bell), tubing, and earpieces. "
            "The diaphragm is used for high-frequency sounds (normal heart sounds, breath sounds); "
            "the bell for low-frequency sounds (third heart sound, mitral stenosis murmur). "
            "Maintenance: clean the diaphragm, bell, and earpieces with 70 % isopropyl alcohol wipe "
            "after each patient contact. "
            "The device should be calibrated and inspected by a biomedical engineer every 12 months "
            "per ISO 17510 and local hospital policy."
        ),
    },
    {
        "domain": "equipment_study",
        "filename": "mri_safety.txt",
        "corpus_id": "eq-002",
        "text": (
            "Magnetic Resonance Imaging (MRI) uses strong static magnetic fields (1.5–3 T for clinical "
            "systems), radiofrequency pulses, and gradient fields to produce anatomical images. "
            "MRI is contraindicated in patients with ferromagnetic implants, certain cardiac pacemakers, "
            "cochlear implants, and metallic ocular foreign bodies. "
            "MR-conditional devices may enter the scanner room only after verification of compatibility "
            "using the manufacturer's MR safety labelling. "
            "All personnel must complete MRI safety screening before entering Zone III or IV. "
            "The scanner bore and gradient coils require preventive maintenance every 6 months; "
            "magnet quench events must be reported to the physics team within 1 hour."
        ),
    },
    {
        "domain": "equipment_study",
        "filename": "defibrillator_protocol.txt",
        "corpus_id": "eq-003",
        "text": (
            "An Automated External Defibrillator (AED) delivers a pre-programmed electrical shock to "
            "terminate ventricular fibrillation (VF) and pulseless ventricular tachycardia (pVT). "
            "AEDs must be inspected monthly: confirm the device status indicator is green, check "
            "electrode pad expiry dates, and verify battery capacity. "
            "Following ILCOR guidelines, the AED should be placed within 1.5 minutes walking distance "
            "of any point in a public-access defibrillation programme. "
            "After each clinical use the device must undergo post-event data download, pad replacement, "
            "and biomedical engineering sign-off before being returned to service. "
            "The recommended shock energy for biphasic AEDs is 120–200 J for VF/pVT."
        ),
    },
]


# ─── Q&A Samples ─────────────────────────────────────────────────────────────
# 3 samples per domain; each references one or more corpus entries above.

SAMPLES: list[dict] = [

    # ── Disease Study ─────────────────────────────────────────────────────────
    {
        "domain": "disease_study",
        "question": "What are the primary symptoms of type 2 diabetes mellitus?",
        "reference": (
            "The primary symptoms of type 2 diabetes mellitus are polydipsia (excessive thirst), "
            "polyuria (frequent urination), polyphagia (increased appetite), unexplained weight loss, "
            "fatigue, blurred vision, and slow-healing wounds."
        ),
        "reference_contexts": [CORPUS[0]["text"]],
    },
    {
        "domain": "disease_study",
        "question": "What are the non-pharmacological interventions for hypertension?",
        "reference": (
            "Non-pharmacological interventions for hypertension include dietary sodium restriction "
            "below 2.3 g/day, regular aerobic exercise, weight reduction, and smoking cessation."
        ),
        "reference_contexts": [CORPUS[1]["text"]],
    },
    {
        "domain": "disease_study",
        "question": "What is the standard empirical antibiotic treatment for non-severe community-acquired pneumonia?",
        "reference": (
            "The standard empirical treatment for non-severe CAP is amoxicillin 500 mg three times "
            "daily (TDS) for 5 days."
        ),
        "reference_contexts": [CORPUS[2]["text"]],
    },

    # ── Medicine Study ────────────────────────────────────────────────────────
    {
        "domain": "medicine_study",
        "question": "How does aspirin inhibit platelet aggregation?",
        "reference": (
            "Aspirin irreversibly inhibits COX-1 enzyme, which blocks thromboxane A2 synthesis "
            "in platelets, thereby inhibiting platelet aggregation. "
            "Low-dose aspirin (75–100 mg/day) is used for secondary prevention of myocardial "
            "infarction and ischaemic stroke."
        ),
        "reference_contexts": [CORPUS[3]["text"]],
    },
    {
        "domain": "medicine_study",
        "question": "What is the mechanism of action of metformin in treating type 2 diabetes?",
        "reference": (
            "Metformin primarily suppresses hepatic gluconeogenesis via activation of "
            "AMP-activated protein kinase (AMPK). It also improves peripheral insulin sensitivity "
            "and reduces intestinal glucose absorption."
        ),
        "reference_contexts": [CORPUS[4]["text"]],
    },
    {
        "domain": "medicine_study",
        "question": "What is the recommended dosage of penicillin V for streptococcal throat infection?",
        "reference": (
            "The typical adult dose of penicillin V for streptococcal throat infection is "
            "250–500 mg every 6 hours for 10 days."
        ),
        "reference_contexts": [CORPUS[5]["text"]],
    },

    # ── Medicine Expiry ───────────────────────────────────────────────────────
    {
        "domain": "medicine_expiry",
        "question": "What are the storage requirements for amoxicillin and how long does reconstituted suspension remain viable?",
        "reference": (
            "Amoxicillin capsules and tablets should be stored at 20–25 °C in a tightly sealed "
            "container, protected from moisture and light, with a shelf life of 2–3 years. "
            "Reconstituted oral suspension must be refrigerated at 2–8 °C and discarded after 14 days."
        ),
        "reference_contexts": [CORPUS[6]["text"]],
    },
    {
        "domain": "medicine_expiry",
        "question": "What temperature must insulin never be exposed to, and why?",
        "reference": (
            "Insulin must never be frozen (below 0 °C) because freezing causes protein denaturation "
            "and renders the insulin ineffective. Unopened vials should be refrigerated between 2 °C "
            "and 8 °C; once opened they can be kept at room temperature below 30 °C for up to 28 days."
        ),
        "reference_contexts": [CORPUS[7]["text"]],
    },
    {
        "domain": "medicine_expiry",
        "question": "How should a healthcare worker assess whether a vaccine has been compromised by a cold-chain breach?",
        "reference": (
            "The Vaccine Vial Monitor (VVM) should be checked before administration. If the inner "
            "square equals or is darker than the outer ring, the vaccine has reached its discard "
            "point and must not be used. Cold-chain breaches must be reported within 24 hours."
        ),
        "reference_contexts": [CORPUS[8]["text"]],
    },

    # ── Equipment Study ───────────────────────────────────────────────────────
    {
        "domain": "equipment_study",
        "question": "How often should a stethoscope be calibrated and what is the cleaning protocol?",
        "reference": (
            "A stethoscope should be calibrated and inspected by a biomedical engineer every 12 months "
            "per ISO 17510. The diaphragm, bell, and earpieces must be cleaned with 70 % isopropyl "
            "alcohol wipe after each patient contact."
        ),
        "reference_contexts": [CORPUS[9]["text"]],
    },
    {
        "domain": "equipment_study",
        "question": "What are the contraindications for MRI scanning?",
        "reference": (
            "MRI is contraindicated in patients with ferromagnetic implants, certain cardiac pacemakers, "
            "cochlear implants, and metallic ocular foreign bodies. MR-conditional devices may only "
            "enter the scanner room after verification of compatibility."
        ),
        "reference_contexts": [CORPUS[10]["text"]],
    },
    {
        "domain": "equipment_study",
        "question": "What monthly checks are required for an AED and what shock energy does it deliver?",
        "reference": (
            "Monthly AED checks include confirming the status indicator is green, checking electrode "
            "pad expiry dates, and verifying battery capacity. Biphasic AEDs deliver 120–200 J for "
            "ventricular fibrillation or pulseless ventricular tachycardia."
        ),
        "reference_contexts": [CORPUS[11]["text"]],
    },
]

# ── Convenience lookup: corpus entries grouped by domain ─────────────────────
CORPUS_BY_DOMAIN: dict[str, list[dict]] = {}
for _entry in CORPUS:
    CORPUS_BY_DOMAIN.setdefault(_entry["domain"], []).append(_entry)
