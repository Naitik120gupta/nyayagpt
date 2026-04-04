// --- DOM Elements ---
const analyzeBtn = document.getElementById('analyze-btn');
const crimeDescription = document.getElementById('crime-description');
const complainantName = document.getElementById('complainant-name');
const accusedDetails = document.getElementById('accused-details');
const incidentAddress = document.getElementById('incident-address');
const incidentDate = document.getElementById('incident-date');
const incidentTime = document.getElementById('incident-time');
const complainantAddress = document.getElementById('complainant-address');
const policeStation = document.getElementById('police-station');
const witnessDetails = document.getElementById('witness-details');
const additionalFacts = document.getElementById('additional-facts');
const smartPreFillForm = document.getElementById('smart-prefill-form');
const generatePreFillBtn = document.getElementById('generate-prefill-btn');

// Right Panel States
const emptyState = document.getElementById('empty-state');
const loadingSpinner = document.getElementById('loading-spinner');
const resultsContent = document.getElementById('results-content');
const voiceBtn = document.getElementById('voice-input-btn');

// --- API Configuration ---
const REMOTE_API_URL = 'https://api.nyayagpt.in';
const LOCAL_API_URL = 'http://localhost:8000';
const urlParams = new URLSearchParams(window.location.search);
const preferLocalApi = urlParams.get('api') === 'local';
const API_BASE_URL = preferLocalApi ? LOCAL_API_URL : REMOTE_API_URL;

let lastLegalToolkit = null;
let lastIncidentMeta = null;

// --- Analyze Logic ---
if (analyzeBtn) {
    analyzeBtn.addEventListener('click', async () => {
        const incidentDescription = crimeDescription.value;
        if (incidentDescription.trim() === '') {
            alert('Please describe the incident first.');
            return;
        }

        const incidentMeta = {
            complainant_name: complainantName?.value?.trim() || '',
            accused_details: accusedDetails?.value?.trim() || '',
            incident_address: incidentAddress?.value?.trim() || '',
            incident_date: incidentDate?.value || '',
            incident_time: incidentTime?.value || '',
        };

        // UI State Updates
        emptyState.classList.add('hidden');
        resultsContent.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');

        try {
            const response = await fetch(`${API_BASE_URL}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: incidentDescription,
                    ...incidentMeta,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const apiResponse = await response.json();
            
            loadingSpinner.classList.add('hidden');
            resultsContent.classList.remove('hidden');

            if (apiResponse.error) {
                renderError(apiResponse.error);
            } else {
                const toolkitPayload = normalizeToolkitPayload(apiResponse.analysis);
                lastLegalToolkit = toolkitPayload;
                lastIncidentMeta = incidentMeta;
                renderLegalAnalysis(toolkitPayload);

                if (smartPreFillForm) smartPreFillForm.classList.remove('hidden');
                analyzeBtn.classList.add('hidden');
                if (generatePreFillBtn) generatePreFillBtn.classList.remove('hidden');
            }

        } catch (error) {
            console.error("Error calling the API:", error);
            loadingSpinner.classList.add('hidden');
            resultsContent.classList.remove('hidden');
            renderError(`Could not connect to NyayaGPT services. Ensure backend is running.`);
        }
    });
}

if (generatePreFillBtn) {
    generatePreFillBtn.addEventListener('click', async () => {
        const incidentDescription = crimeDescription.value;
        if (incidentDescription.trim() === '') {
            alert('Please describe the incident first.');
            return;
        }

        const incidentMeta = {
            complainant_name: complainantName?.value?.trim() || '',
            complainant_address: complainantAddress?.value?.trim() || '',
            accused_details: accusedDetails?.value?.trim() || '',
            incident_address: incidentAddress?.value?.trim() || '',
            incident_date: incidentDate?.value || '',
            incident_time: incidentTime?.value || '',
            police_station: policeStation?.value?.trim() || '',
            witness_details: witnessDetails?.value?.trim() || '',
            additional_facts: additionalFacts?.value?.trim() || '',
        };

        emptyState.classList.add('hidden');
        resultsContent.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');

        try {
            const response = await fetch(`${API_BASE_URL}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: incidentDescription,
                    ...incidentMeta,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const apiResponse = await response.json();
            loadingSpinner.classList.add('hidden');
            resultsContent.classList.remove('hidden');

            if (apiResponse.error) {
                renderError(apiResponse.error);
                return;
            }

            const toolkitPayload = normalizeToolkitPayload(apiResponse.analysis);
            renderSmartPreFill(toolkitPayload, incidentMeta);
        } catch (error) {
            console.error('Error calling the API:', error);
            loadingSpinner.classList.add('hidden');
            resultsContent.classList.remove('hidden');
            renderError('Could not connect to NyayaGPT services. Ensure backend is running.');
        }
    });
}

// --- Voice Input Logic ---
if (voiceBtn) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false; 
        recognition.lang = 'en-US'; 
        recognition.interimResults = false;

        let isRecording = false;

        voiceBtn.addEventListener('click', () => {
            if (isRecording) {
                recognition.stop();
            } else {
                recognition.start();
            }
        });

        recognition.onstart = () => {
            isRecording = true;
            voiceBtn.classList.add('border-red-500', 'text-red-500', 'bg-red-500/10');
            voiceBtn.innerHTML = '<i class="fas fa-stop"></i> Stop';
        };

        recognition.onend = () => {
            isRecording = false;
            voiceBtn.classList.remove('border-red-500', 'text-red-500', 'bg-red-500/10');
            voiceBtn.innerHTML = '<i class="fas fa-microphone"></i> Dictate';
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            if (crimeDescription.value.trim() !== "") {
                crimeDescription.value += " " + transcript;
            } else {
                crimeDescription.value = transcript;
            }
        };

        recognition.onerror = (event) => {
            isRecording = false;
            alert("Error with voice input: " + event.error);
        };
    } else {
        voiceBtn.style.display = 'none'; 
    }
}

// --- Render Logic ---
function normalizeToolkitPayload(payload) {
    if (typeof payload === 'string') {
        try { return JSON.parse(payload); } catch { return null; }
    }
    return payload && typeof payload === 'object' ? payload : null;
}

function buildFormattedPreFillText(toolkit, incidentMeta) {
    const sections = Array.isArray(toolkit?.legal_analysis?.sections) ? toolkit.legal_analysis.sections : [];
    const sectionsText = sections.length
        ? sections.map(section => `• ${section}`).join('\n')
        : '• Not available';

    const complainant = incidentMeta.complainant_name || 'Not Provided';
    const complainantAddress = incidentMeta.complainant_address || '[Complainant Address - To be filled by Complainant]';
    const policeStation = incidentMeta.police_station || '[Name of Police Station - To be filled by Complainant]';
    const policeStationAddress = '[Address of Police Station - To be filled by Complainant]';
    const accused = incidentMeta.accused_details || 'Unknown';
    const date = incidentMeta.incident_date || 'Not Provided';
    const time = incidentMeta.incident_time || 'Not Provided';
    const address = incidentMeta.incident_address || 'Not Provided';
    const complaintSubject = toolkit?.smart_pre_fill?.title
        ? `FIR regarding ${toolkit.smart_pre_fill.title.replace(/^FIR Preparation Summary\s*/i, '').trim() || 'the reported incident.'}`
        : 'FIR regarding the reported incident.';
    const generatedNarrative = (toolkit?.smart_pre_fill?.draft_text || '').trim();

    const narrative = `To,
The Station House Officer,
${policeStation}
${policeStationAddress}

Subject: ${complaintSubject}

Respected Sir/Madam,

I, ${complainant}, resident of ${complainantAddress},
wish to report an incident that occurred on ${date} at approximately ${time}.

On the aforementioned date and time, at ${address}, the following incident occurred:
${generatedNarrative || '[Describe incident in chronological order - To be filled by Complainant]'}

Accused details (if known): ${accused}

The details of stolen/lost/damaged property (if applicable) are as follows:
[Provide Make, Model, Serial Number, Color, value, any distinguishing features - To be filled by Complainant]

Witness details (if any): ${incidentMeta.witness_details || '[Witness details - To be filled by Complainant]'}

I request that you kindly register a First Information Report under the relevant sections of the Bharatiya Nyaya Sanhita, 2023, and take necessary action to investigate this matter.

Thank you.

Sincerely,
${complainant}
[Complainant Contact Details - To be filled by Complainant]`;

    return `FIR Preparation Summary - NyayaGPT Smart Pre-Fill
NOT AN OFFICIAL FIR - AI PRE-FILL DATA FOR CCTNS IIF-1
1. Incident & Entity Details
Complainant: ${complainant}
Accused: ${accused}
Date: ${date}
Time: ${time}
Address: ${address}
2. AI-Identified BNS Sections
${sectionsText}
3. Structured Complaint Narrative
${narrative}`;
}

function renderLegalAnalysis(toolkit) {
    if (!toolkit) {
        resultsContent.innerHTML = '<p class="text-slate-400">No structured legal toolkit returned.</p>';
        return;
    }

    const validation = toolkit.validation_layer || {};
    const legal = toolkit.legal_analysis || {};
    const route = toolkit.route_recommendation || {};
    const rights = toolkit.rights_reminder || {};
    
    const sections = Array.isArray(legal.sections) ? legal.sections : [];
    const sectionsHtml = sections.map(section => `<li class="mb-1 text-slate-300">• ${section}</li>`).join('');
    const warnings = Array.isArray(validation.warnings) ? validation.warnings : [];
    const warningsHtml = warnings.length
        ? `<div class="toolkit-card border border-amber-400/40 bg-amber-500/10">
                <h4 class="text-amber-300 font-semibold mb-2 flex items-center gap-2">
                    <i class="fas fa-triangle-exclamation"></i> AI Validation Warnings
                </h4>
                <ul class="text-sm text-amber-100 space-y-1">${warnings.map(item => `<li>• ${item}</li>`).join('')}</ul>
            </div>`
        : '';

    const offenseCategory = validation.offense_category || 'Not available';
    const routeButtonHtml = route.portal_link
        ? `<a href="${route.portal_link}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2 mt-3 px-4 py-2.5 bg-emerald-400 text-slate-900 font-semibold rounded-lg hover:bg-emerald-300 transition-colors">
                <i class="fas fa-arrow-up-right-from-square"></i> Go to State e-FIR Portal
           </a>`
        : '';

    resultsContent.innerHTML = `
        ${warningsHtml}

        <div class="toolkit-card toolkit-legal">
            <h4 class="text-sky-400 font-semibold mb-3 flex items-center gap-2">
                <i class="fas fa-book-open"></i> Legal Analysis (BNS)
            </h4>
            <ul class="mb-3 text-sm">${sectionsHtml}</ul>
            <p class="text-sm text-slate-300 mb-2"><strong class="text-slate-100">Validation:</strong> ${validation.is_valid === false ? 'Needs Review' : 'Looks Consistent'}</p>
            <p class="text-sm text-slate-300 mb-2"><strong class="text-slate-100">Offense Category:</strong> ${offenseCategory}</p>
            <p class="text-sm text-slate-300 mb-2"><strong class="text-slate-100">Explanation:</strong> ${legal.explanation || 'N/A'}</p>
            <p class="text-sm text-slate-300 mb-2"><strong class="text-slate-100">Nature:</strong> ${legal.nature || 'N/A'}</p>
            <p class="text-sm text-slate-300"><strong class="text-slate-100">Punishment:</strong> ${legal.punishment || 'N/A'}</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="toolkit-card toolkit-route">
                <h4 class="text-emerald-400 font-semibold mb-2 flex items-center gap-2">
                    <i class="fas fa-route"></i> Next Steps
                </h4>
                <p class="text-sm text-slate-300"><strong class="text-slate-100">Action:</strong> ${route.action_type || 'N/A'}</p>
                <p class="text-sm text-slate-300 mt-1">${route.instructions || ''}</p>
                ${routeButtonHtml}
            </div>
            <div class="toolkit-card toolkit-rights">
                <h4 class="text-red-400 font-semibold mb-2 flex items-center gap-2">
                    <i class="fas fa-shield-halved"></i> Know Your Rights
                </h4>
                <p class="text-sm text-slate-300">${rights.text || ''}</p>
            </div>
        </div>
    `;
}

function renderSmartPreFill(toolkit, incidentMeta) {
    if (!toolkit) {
        resultsContent.innerHTML = '<p class="text-slate-400">No Smart Pre-Fill generated.</p>';
        return;
    }

    const formattedPreFillText = buildFormattedPreFillText(toolkit, incidentMeta);

    resultsContent.innerHTML = `
        <div class="toolkit-card toolkit-summary">
            <div class="flex justify-between items-center mb-3 flex-wrap gap-2">
                <h4 class="text-orange-400 font-semibold flex items-center gap-2">
                    <i class="fas fa-file-lines"></i> FIR Preparation Summary (Smart Pre-Fill)
                </h4>
                <div class="flex gap-2 flex-wrap">
                    <button id="copy-summary-btn" class="text-xs px-3 py-1.5 bg-orange-400/20 text-orange-400 border border-orange-400/30 rounded-full hover:bg-orange-400/30 transition-colors flex items-center gap-1.5">
                        <i class="fas fa-copy"></i> Copy Text
                    </button>
                    <button id="download-txt-btn" class="text-xs px-3 py-1.5 bg-emerald-400/20 text-emerald-300 border border-emerald-400/30 rounded-full hover:bg-emerald-400/30 transition-colors flex items-center gap-1.5">
                        <i class="fas fa-file-arrow-down"></i> Download .txt
                    </button>
                    <button id="download-pdf-btn" class="text-xs px-3 py-1.5 bg-sky-400/20 text-sky-400 border border-sky-400/30 rounded-full hover:bg-sky-400/30 transition-colors flex items-center gap-1.5">
                        <i class="fas fa-file-pdf"></i> Save PDF
                    </button>
                </div>
            </div>
            <div class="mb-3">
                <span class="inline-block px-2 py-1 bg-red-500/20 text-red-400 border border-red-500/30 text-[10px] uppercase font-bold rounded tracking-wider">
                    NOT AN OFFICIAL FIR - AI PRE-FILL DATA
                </span>
            </div>
            <textarea id="editable-prefill-text" rows="18" class="ghost-input w-full resize-y">${formattedPreFillText}</textarea>
        </div>
    `;

    document.getElementById('copy-summary-btn')?.addEventListener('click', async (e) => {
        try {
            const currentText = document.getElementById('editable-prefill-text')?.value || '';
            await navigator.clipboard.writeText(currentText);
            e.currentTarget.innerHTML = '<i class="fas fa-check"></i> Copied';
            setTimeout(() => e.currentTarget.innerHTML = '<i class="fas fa-copy"></i> Copy Text', 2000);
        } catch (err) {
            alert('Failed to copy. Please select the text manually.');
        }
    });

    document.getElementById('download-txt-btn')?.addEventListener('click', () => {
        const currentText = document.getElementById('editable-prefill-text')?.value || '';
        const blob = new Blob([currentText], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'NyayaGPT_Smart_PreFill.txt';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    });

    document.getElementById('download-pdf-btn')?.addEventListener('click', () => {
        downloadToolkitPdf(toolkit, incidentMeta);
    });
}

// --- New PDF Generator Function ---
function downloadToolkitPdf(toolkit, incidentMeta) {
    const jsPDF = window.jspdf?.jsPDF;
    if (!jsPDF) {
        alert('PDF library failed to load. Please check your internet connection.');
        return;
    }

    const doc = new jsPDF({ unit: 'pt', format: 'a4' });
    const margin = 40;
    const pageWidth = doc.internal.pageSize.getWidth();
    const maxLineWidth = pageWidth - margin * 2;
    let y = 50;

    const fullText = document.getElementById('editable-prefill-text')?.value || buildFormattedPreFillText(toolkit, incidentMeta);
    const lines = fullText.split('\n');

    lines.forEach((line, index) => {
        const trimmed = line.trim();
        const isHeader = index === 0;
        const isDisclaimer = index === 1;
        const isSectionHeading = /^\d+\.\s/.test(trimmed);

        if (isHeader) {
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(16);
            doc.setTextColor(0, 0, 0);
        } else if (isDisclaimer) {
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(10);
            doc.setTextColor(220, 38, 38);
        } else if (isSectionHeading) {
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(12);
            doc.setTextColor(0, 0, 0);
        } else {
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(10);
            doc.setTextColor(0, 0, 0);
        }

        const wrapped = doc.splitTextToSize(line, maxLineWidth);
        wrapped.forEach(wrappedLine => {
            if (y > doc.internal.pageSize.getHeight() - margin) {
                doc.addPage();
                y = margin;
            }
            doc.text(wrappedLine, margin, y);
            y += 14;
        });

        y += isHeader || isDisclaimer || isSectionHeading ? 4 : 2;
    });

    // Save the Document
    doc.save('NyayaGPT_Complaint_Summary.pdf');
}

function renderError(errorMessage) {
    resultsContent.innerHTML = `
        <div class="p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
            <h3 class="text-red-400 font-semibold mb-1"><i class="fas fa-triangle-exclamation"></i> Error</h3>
            <p class="text-sm text-slate-300">${errorMessage}</p>
        </div>`;
}