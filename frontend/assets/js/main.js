// --- DOM Elements ---
const analyzeBtn = document.getElementById('analyze-btn');
const backBtn = document.getElementById('back-btn');
const crimeDescription = document.getElementById('crime-description');
const screenAnalyze = document.getElementById('screen-analyze');
const screenResults = document.getElementById('screen-results');
const screenFirForm = document.getElementById('screen-fir-form');
const screenFirResult = document.getElementById('screen-fir-result');
const userQueryDisplay = document.getElementById('user-query-display');
const resultsContent = document.getElementById('results-content');
const loadingSpinner = document.getElementById('loading-spinner');
const voiceBtn = document.getElementById('voice-input-btn');
const firAction = document.getElementById('fir-action');
const gotoFirBtn = document.getElementById('goto-fir-btn');
const backFromFirBtn = document.getElementById('back-from-fir-btn');
const firForm = document.getElementById('fir-form');
const firLoadingSpinner = document.getElementById('fir-loading-spinner');
const firResultContent = document.getElementById('fir-result-content');
const printFirBtn = document.getElementById('print-fir-btn');
const startOverBtn = document.getElementById('start-over-btn');

// --- API Configuration ---
const REMOTE_API_URL = 'https://nyayagpt.onrender.com';
const LOCAL_API_URL = 'http://localhost:8000';
const urlParams = new URLSearchParams(window.location.search);
const preferLocalApi = urlParams.get('api') === 'local';
// Add ?api=local to the URL when you want to force a local backend during development.
const API_BASE_URL = preferLocalApi ? LOCAL_API_URL : REMOTE_API_URL;

// --- State ---
let lastAnalysisText = '';
let lastQuery = '';
let lastFirFormData = null;

// --- Helper: hide all screens ---
function showScreen(screenEl) {
    [screenAnalyze, screenResults, screenFirForm, screenFirResult].forEach(s => s.classList.add('hidden'));
    screenEl.classList.remove('hidden');
}

// --- Analyze ---
if (analyzeBtn) {
    analyzeBtn.addEventListener('click', async () => {
        const incidentDescription = crimeDescription.value;
        if (incidentDescription.trim() === '') {
            alert('Please describe the incident first.');
            return;
        }

        lastQuery = incidentDescription;
        showScreen(screenResults);
        userQueryDisplay.textContent = `"${incidentDescription}"`;
        loadingSpinner.classList.remove('hidden');
        resultsContent.innerHTML = '';
        firAction.classList.add('hidden');

        try {
            const response = await fetch(`${API_BASE_URL}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: incidentDescription }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const apiResponse = await response.json();
            loadingSpinner.classList.add('hidden');

            if (apiResponse.error) {
                renderError(apiResponse.error, resultsContent);
            } else {
                lastAnalysisText = apiResponse.analysis;
                renderResults(apiResponse.analysis);
                firAction.classList.remove('hidden');
            }

        } catch (error) {
            console.error("Error calling the API:", error);
            loadingSpinner.classList.add('hidden');
            renderError(`Could not connect to NyayaGPT services at ${API_BASE_URL}. If you intend to use a local backend, append ?api=local to the URL and ensure ${LOCAL_API_URL} is running.`, resultsContent);
        }
    });
}

// --- Back from Results ---
if (backBtn) {
    backBtn.addEventListener('click', () => {
        showScreen(screenAnalyze);
        crimeDescription.value = '';
        lastAnalysisText = '';
        lastQuery = '';
    });
}

// --- Go to FIR Form ---
if (gotoFirBtn) {
    gotoFirBtn.addEventListener('click', () => {
        showScreen(screenFirForm);
    });
}

// --- Back from FIR Form ---
if (backFromFirBtn) {
    backFromFirBtn.addEventListener('click', () => {
        showScreen(screenResults);
    });
}

// --- FIR Form Submit ---
if (firForm) {
    firForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const firData = {
            incident: {
                ps: document.getElementById('fir-ps').value,
                dist: document.getElementById('fir-dist').value,
                date: document.getElementById('fir-date').value,
                time: document.getElementById('fir-time').value,
                place: document.getElementById('fir-place').value,
            },
            complainant: {
                name: document.getElementById('fir-complainant-name').value,
                guardian: document.getElementById('fir-guardian').value,
                address: document.getElementById('fir-complainant-address').value,
            },
            accused: {
                details: document.getElementById('fir-accused').value,
                witnesses: document.getElementById('fir-witnesses').value,
            },
            aiAnalysis: lastAnalysisText,
            crimeDescription: lastQuery,
        };

        lastFirFormData = firData;

        showScreen(screenFirResult);
        firResultContent.textContent = '';
        firLoadingSpinner.classList.remove('hidden');

        try {
            const response = await fetch(`${API_BASE_URL}/generate-fir`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ firData }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const apiResponse = await response.json();
            firLoadingSpinner.classList.add('hidden');

            if (apiResponse.fir_text) {
                renderFirDraft(firData, apiResponse.fir_text);
            } else {
                renderError("Failed to generate FIR document.", firResultContent);
            }

        } catch (error) {
            console.error("Error generating FIR:", error);
            firLoadingSpinner.classList.add('hidden');
            renderError(`Could not connect to NyayaGPT services at ${API_BASE_URL}. If you intend to use a local backend, append ?api=local to the URL and ensure ${LOCAL_API_URL} is running.`, firResultContent);
        }
    });
}

// --- Print FIR ---
if (printFirBtn) {
    printFirBtn.addEventListener('click', () => {
        const content = firResultContent.textContent;
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`<html><head><title>FIR Draft</title><style>body{font-family:monospace;padding:2rem;white-space:pre-wrap}</style></head><body>${content}</body></html>`);
        printWindow.document.close();
        printWindow.print();
    });
}

// --- Start Over ---
if (startOverBtn) {
    startOverBtn.addEventListener('click', () => {
        showScreen(screenAnalyze);
        crimeDescription.value = '';
        lastAnalysisText = '';
        lastQuery = '';
        firForm.reset();
        firResultContent.innerHTML = '';
    });
}

// --- Voice Input Logic ---
if (voiceBtn) {
    // Check for browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false; // Stop after one sentence/phrase
        recognition.lang = 'en-US'; // Default to English, could be made configurable
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
            voiceBtn.classList.remove('text-gray-400');
            voiceBtn.classList.add('text-red-600', 'animate-pulse');
            voiceBtn.title = "Stop Recording";
        };

        recognition.onend = () => {
            isRecording = false;
            voiceBtn.classList.remove('text-red-600', 'animate-pulse');
            voiceBtn.classList.add('text-gray-400');
            voiceBtn.title = "Start Voice Input";
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;

            // Append to existing text if any, with a space
            if (crimeDescription.value.trim() !== "") {
                crimeDescription.value += " " + transcript;
            } else {
                crimeDescription.value = transcript;
            }
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error", event.error);
            isRecording = false;
            voiceBtn.classList.remove('text-red-600', 'animate-pulse');
            voiceBtn.classList.add('text-gray-400');
            alert("Error with voice input: " + event.error);
        };

    } else {
        voiceBtn.style.display = 'none'; // Hide button if not supported
        console.warn("Speech Recognition API not supported in this browser.");
    }
}

function renderResults(rawAnalysisText) {
    if (!rawAnalysisText) {
        resultsContent.innerHTML = '<p class="text-slate-400">No analysis returned.</p>';
        return;
    }

    const normalized = rawAnalysisText.replace(/\r/g, '').trim();
    const headingApplied = normalized.replace(/\*\*(.*?)\*\*/g, '<h3>$1</h3>');
    const blocks = headingApplied.split(/\n{2,}/).map(block => block.trim()).filter(Boolean);

    const html = blocks.map(block => {
        if (block.startsWith('<h3>')) {
            return `${block.replace(/\n/g, '<br>')}`;
        }
        return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    resultsContent.innerHTML = html;
}

function renderError(errorMessage, container) {
    const target = container || resultsContent;
    target.innerHTML = `<div class="text-center p-4 bg-red-100 border border-red-300 rounded-lg">
        <h3 class="font-semibold text-red-800">An Error Occurred</h3>
        <p class="text-red-700">${errorMessage}</p>
    </div>`;
}

function renderFirDraft(firData, firNarrative) {
    lastFirFormData = firData;
    const firHtml = buildFirHtml(firData, firNarrative);
    firResultContent.innerHTML = firHtml;
}

function buildFirHtml(firData, firNarrative) {
    const { incident, complainant, accused } = firData;
    const narrativeHtml = formatNarrative(firNarrative || 'Narrative unavailable.');

    return `
        <section class="fir-sheet">
            <header class="fir-header">
                <div>
                    <p class="fir-eyebrow">First Information Report · Draft Copy</p>
                    <h3>Under Section 154 Cr.P.C.</h3>
                </div>
                <div class="fir-meta">Prepared via NyayaGPT</div>
            </header>

            <div class="fir-grid">
                <div class="fir-cell"><span>Police Station</span><p>${incident.ps || '—'}</p></div>
                <div class="fir-cell"><span>District</span><p>${incident.dist || '—'}</p></div>
                <div class="fir-cell"><span>FIR No.</span><p>To be assigned</p></div>
                <div class="fir-cell"><span>Year</span><p>${new Date().getFullYear()}</p></div>
                <div class="fir-cell"><span>Date & Time of Information</span><p>${new Date().toLocaleString()}</p></div>
                <div class="fir-cell"><span>Date & Time of Occurrence</span><p>${incident.date || '—'} ${incident.time || ''}</p></div>
                <div class="fir-cell"><span>Place of Occurrence</span><p>${incident.place || '—'}</p></div>
            </div>

            <section class="fir-columns">
                <article>
                    <h4>Complainant Details</h4>
                    <p><strong>Name:</strong> ${complainant.name || '—'}</p>
                    <p><strong>Father/Guardian:</strong> ${complainant.guardian || '—'}</p>
                    <p><strong>Address:</strong> ${complainant.address || '—'}</p>
                </article>
                <article>
                    <h4>Accused & Witnesses</h4>
                    <p><strong>Accused:</strong> ${accused.details || 'Unknown'}</p>
                    <p><strong>Witnesses:</strong> ${accused.witnesses || '—'}</p>
                </article>
            </section>

            <section class="fir-narrative">
                <h4>Statement of Information</h4>
                ${narrativeHtml}
            </section>

            <footer class="fir-footer">
                <p>This document is a draft FIR generated for review. Please verify and record it in the official register before action.</p>
                <div class="fir-signature">
                    <div>
                        <span>Signature of Informant</span>
                        <p>${complainant.name || '________________'}</p>
                    </div>
                    <div>
                        <span>Receiving Officer</span>
                        <p>________________</p>
                    </div>
                </div>
            </footer>
        </section>
    `;
}

function formatNarrative(text) {
    const cleaned = text.replace(/\*\*(.*?)\*\*/g, '$1').trim();
    const paragraphs = cleaned.split(/\n+/).map(p => `<p>${p}</p>`).join('');
    return paragraphs;
}
