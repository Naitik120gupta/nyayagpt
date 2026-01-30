// --- DOM Elements ---
const analyzeBtn = document.getElementById('analyze-btn');
const backBtn = document.getElementById('back-btn');
const crimeDescription = document.getElementById('crime-description');
const screenAnalyze = document.getElementById('screen-analyze');
const screenResults = document.getElementById('screen-results');
const userQueryDisplay = document.getElementById('user-query-display');
const resultsContent = document.getElementById('results-content');
const loadingSpinner = document.getElementById('loading-spinner');

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

const voiceBtn = document.getElementById('voice-input-btn');
if (voiceBtn) {
    voiceBtn.addEventListener('click', () => {
        alert("Voice Input feature is coming soon!");
    });
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
