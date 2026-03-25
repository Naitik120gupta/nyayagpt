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
// Change this URL to your deployed backend URL (e.g., https://nyayagpt-api.onrender.com)
// If running locally, keep it as http://localhost:8000
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:8000' 
    : 'https://nyayagpt-backend.onrender.com'; 

// --- State ---
let lastAnalysisText = '';
let lastQuery = '';

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
                renderResults(apiResponse.analysis.replace(/\*\*(.*?)\*\*/g, '<h3>$1</h3>').replace(/\*/g, '<br>'));
                firAction.classList.remove('hidden');
            }

        } catch (error) {
            console.error("Error calling the API:", error);
            loadingSpinner.classList.add('hidden');
            renderError("Could not connect to the analysis server. Please ensure the backend is running at " + API_BASE_URL, resultsContent);
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
                firResultContent.textContent = apiResponse.fir_text;
            } else {
                renderError("Failed to generate FIR document.", firResultContent);
            }

        } catch (error) {
            console.error("Error generating FIR:", error);
            firLoadingSpinner.classList.add('hidden');
            renderError("Could not connect to the server. Please ensure the backend is running.", firResultContent);
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
        firResultContent.textContent = '';
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

function renderResults(formattedAnalysisHtml) {
    resultsContent.innerHTML = formattedAnalysisHtml;
}

function renderError(errorMessage, container) {
    const target = container || resultsContent;
    target.innerHTML = `<div class="text-center p-4 bg-red-100 border border-red-300 rounded-lg">
        <h3 class="font-semibold text-red-800">An Error Occurred</h3>
        <p class="text-red-700">${errorMessage}</p>
    </div>`;
}
