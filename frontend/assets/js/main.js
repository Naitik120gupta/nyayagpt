// --- DOM Elements ---
const analyzeBtn = document.getElementById('analyze-btn');
const crimeDescription = document.getElementById('crime-description');
const complainantName = document.getElementById('complainant-name');
const accusedDetails = document.getElementById('accused-details');
const incidentAddress = document.getElementById('incident-address');
const incidentDate = document.getElementById('incident-date');
const incidentTime = document.getElementById('incident-time');

// Right Panel States
const emptyState = document.getElementById('empty-state');
const loadingSpinner = document.getElementById('loading-spinner');
const resultsContent = document.getElementById('results-content');
const voiceBtn = document.getElementById('voice-input-btn');

// --- API Configuration ---
const REMOTE_API_URL = 'https://nyayagpt.onrender.com';
const LOCAL_API_URL = 'http://localhost:8000';
const urlParams = new URLSearchParams(window.location.search);
const preferLocalApi = urlParams.get('api') === 'local';
const API_BASE_URL = preferLocalApi ? LOCAL_API_URL : REMOTE_API_URL;

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
                renderToolkit(toolkitPayload, incidentMeta);
            }

        } catch (error) {
            console.error("Error calling the API:", error);
            loadingSpinner.classList.add('hidden');
            resultsContent.classList.remove('hidden');
            renderError(`Could not connect to NyayaGPT services. Ensure backend is running.`);
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

function renderToolkit(toolkit, incidentMeta) {
    if (!toolkit) {
        resultsContent.innerHTML = '<p class="text-slate-400">No structured legal toolkit returned.</p>';
        return;
    }

    const legal = toolkit.legal_analysis || {};
    const route = toolkit.route_recommendation || {};
    const summary = toolkit.complaint_summary || {};
    const rights = toolkit.rights_reminder || {};
    
    const sections = Array.isArray(legal.sections) ? legal.sections : [];
    const sectionsHtml = sections.map(section => `<li class="mb-1 text-slate-300">• ${section}</li>`).join('');

    const tehrirText = summary.draft_text || 'No draft summary generated.';

    resultsContent.innerHTML = `
        <div class="toolkit-card toolkit-legal">
            <h4 class="text-sky-400 font-semibold mb-3 flex items-center gap-2">
                <i class="fas fa-book-open"></i> Legal Analysis (BNS)
            </h4>
            <ul class="mb-3 text-sm">${sectionsHtml}</ul>
            <p class="text-sm text-slate-300 mb-2"><strong class="text-slate-100">Explanation:</strong> ${legal.explanation || 'N/A'}</p>
            <p class="text-sm text-slate-300 mb-2"><strong class="text-slate-100">Nature:</strong> ${legal.nature || 'N/A'}</p>
            <p class="text-sm text-slate-300"><strong class="text-slate-100">Punishment:</strong> ${legal.punishment || 'N/A'}</p>
        </div>

        <div class="toolkit-card toolkit-summary">
            <div class="flex justify-between items-center mb-3 flex-wrap gap-2">
                <h4 class="text-orange-400 font-semibold flex items-center gap-2">
                    <i class="fas fa-file-lines"></i> ${summary.title || 'Complaint Summary'}
                </h4>
                <div class="flex gap-2">
                    <button id="copy-summary-btn" class="text-xs px-3 py-1.5 bg-orange-400/20 text-orange-400 border border-orange-400/30 rounded-full hover:bg-orange-400/30 transition-colors flex items-center gap-1.5">
                        <i class="fas fa-copy"></i> Copy Text
                    </button>
                    <button id="download-pdf-btn" class="text-xs px-3 py-1.5 bg-sky-400/20 text-sky-400 border border-sky-400/30 rounded-full hover:bg-sky-400/30 transition-colors flex items-center gap-1.5">
                        <i class="fas fa-file-pdf"></i> Save PDF
                    </button>
                </div>
            </div>
            <div class="mb-3">
                <span class="inline-block px-2 py-1 bg-red-500/20 text-red-400 border border-red-500/30 text-[10px] uppercase font-bold rounded tracking-wider">
                    Not an official FIR - For Reference Only
                </span>
            </div>
            <div class="draft-box">
                ${tehrirText.replace(/\n/g, '<br>')}
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="toolkit-card toolkit-route">
                <h4 class="text-emerald-400 font-semibold mb-2 flex items-center gap-2">
                    <i class="fas fa-route"></i> Next Steps
                </h4>
                <p class="text-sm text-slate-300"><strong class="text-slate-100">Action:</strong> ${route.action_type || 'N/A'}</p>
                <p class="text-sm text-slate-300 mt-1">${route.instructions || ''}</p>
            </div>
            <div class="toolkit-card toolkit-rights">
                <h4 class="text-red-400 font-semibold mb-2 flex items-center gap-2">
                    <i class="fas fa-shield-halved"></i> Know Your Rights
                </h4>
                <p class="text-sm text-slate-300">${rights.text || ''}</p>
            </div>
        </div>
    `;

    // Copy to Clipboard Listener
    document.getElementById('copy-summary-btn')?.addEventListener('click', async (e) => {
        try {
            await navigator.clipboard.writeText(tehrirText);
            e.currentTarget.innerHTML = '<i class="fas fa-check"></i> Copied';
            setTimeout(() => e.currentTarget.innerHTML = '<i class="fas fa-copy"></i> Copy Text', 2000);
        } catch (err) {
            alert('Failed to copy. Please select the text manually.');
        }
    });

    // Download PDF Listener
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

    // 1. Header & Title
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(16);
    doc.text('Citizen Complaint Summary (Tehrir)', margin, y);
    y += 20;

    // 2. Disclaimer (Red)
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.setTextColor(220, 38, 38); 
    doc.text('NOT AN OFFICIAL FIR - FOR REFERENCE ONLY', margin, y);
    y += 25;
    doc.setTextColor(0, 0, 0); // Reset text color to black

    // 3. Incident Metadata
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text('1. Incident Details', margin, y);
    y += 15;
    
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    const metaLines = [
        `Complainant: ${incidentMeta.complainant_name || 'Not Provided'}`,
        `Accused: ${incidentMeta.accused_details || 'Not Provided'}`,
        `Date: ${incidentMeta.incident_date || 'Not Provided'}`,
        `Time: ${incidentMeta.incident_time || 'Not Provided'}`,
        `Address: ${incidentMeta.incident_address || 'Not Provided'}`
    ];
    
    metaLines.forEach(line => {
        doc.text(line, margin + 10, y);
        y += 14;
    });
    y += 15;

    // 4. Applicable Legal Sections (BNS)
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text('2. Applicable Legal Sections (BNS)', margin, y);
    y += 15;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    const sections = toolkit.legal_analysis?.sections || [];
    if (sections.length > 0) {
        sections.forEach(sec => {
            const splitSec = doc.splitTextToSize(`• ${sec}`, maxLineWidth - 10);
            doc.text(splitSec, margin + 10, y);
            y += splitSec.length * 14;
        });
    } else {
        doc.text('No specific sections identified.', margin + 10, y);
        y += 14;
    }
    y += 15;

    // 5. Draft Text / Narrative
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text('3. Draft Complaint Narrative', margin, y);
    y += 15;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    const draftText = toolkit.complaint_summary?.draft_text || 'No narrative provided.';
    const splitDraft = doc.splitTextToSize(draftText, maxLineWidth);
    
    // Ensure text wraps properly and creates new pages if it gets too long
    splitDraft.forEach(line => {
        if (y > doc.internal.pageSize.getHeight() - margin) {
            doc.addPage();
            y = margin;
        }
        doc.text(line, margin, y);
        y += 14;
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