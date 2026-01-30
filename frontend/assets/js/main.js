// --- DOM Elements ---
const analyzeBtn = document.getElementById('analyze-btn');
const backBtn = document.getElementById('back-btn');
const crimeDescription = document.getElementById('crime-description');
const screenAnalyze = document.getElementById('screen-analyze');
const screenResults = document.getElementById('screen-results');
const userQueryDisplay = document.getElementById('user-query-display');
const resultsContent = document.getElementById('results-content');
const loadingSpinner = document.getElementById('loading-spinner');
const voiceBtn = document.getElementById('voice-input-btn');

// --- API Configuration ---
// Updated to point to local backend for now.
const API_URL = 'http://localhost:8000/analyze';

// --- Event Listeners ---
if (analyzeBtn) {
    analyzeBtn.addEventListener('click', async () => {
        const incidentDescription = crimeDescription.value;
        if (incidentDescription.trim() === '') {
            alert('Please describe the incident first.');
            return;
        }

        // Show results screen and loading spinner
        screenAnalyze.classList.add('hidden');
        screenResults.classList.remove('hidden');
        userQueryDisplay.textContent = `"${incidentDescription}"`;
        loadingSpinner.classList.remove('hidden');
        resultsContent.innerHTML = '';

        try {
            // --- Call the Backend API ---
            const response = await fetch(API_URL, {
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
                renderError(apiResponse.error);
            } else {
                // Simple formatter for the AI's markdown-like response
                renderResults(apiResponse.analysis.replace(/\*\*(.*?)\*\*/g, '<h3>$1</h3>').replace(/\*/g, '<br>'));
            }

        } catch (error) {
            console.error("Error calling the API:", error);
            loadingSpinner.classList.add('hidden');
            renderError("Could not connect to the analysis server. Please ensure the backend is running at " + API_URL);
        }
    });
}

if (backBtn) {
    backBtn.addEventListener('click', () => {
        screenResults.classList.add('hidden');
        screenAnalyze.classList.remove('hidden');
        crimeDescription.value = '';
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

function renderError(errorMessage) {
    resultsContent.innerHTML = `<div class="text-center p-4 bg-red-100 border border-red-300 rounded-lg">
        <h3 class="font-semibold text-red-800">An Error Occurred</h3>
        <p class="text-red-700">${errorMessage}</p>
    </div>`;
}
