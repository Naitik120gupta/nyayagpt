# Contributing to Nyay Sahayak 🤝

First off, thank you for considering contributing to Nyay Sahayak! It's people like you that make the open-source community such an amazing place to learn, inspire, and create.

We welcome contributions of all forms—whether it's fixing a bug, improving the documentation, suggesting a new feature, or adding more legal data to our knowledge base.

## 🚀 How to Get Started

### 1. Fork and Clone
1.  Fork the repository to your own GitHub account.
2.  Clone the project to your local machine:
    ```bash
    git clone [https://github.com/your-username/nyay-sahayak.git](https://github.com/your-username/nyay-sahayak.git)
    cd nyay-sahayak
    ```

### 2. Set Up Your Environment
To ensure your code runs correctly, please follow the setup steps:

1.  **Backend Setup:**
    ```bash
    cd backend
    python -m venv venv
    # Windows:
    .\venv\Scripts\activate
    # Mac/Linux:
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Environment Variables:**
    Create a `.env` file in the `backend` folder and add your Gemini API Key:
    ```env
    GEMINI_API_KEY="your_api_key_here"
    ```

3.  **Build the Database:**
    If you are changing how data is ingested, run:
    ```bash
    python ingest.py
    ```

### 3. Create a Branch
Always create a new branch for your changes. Do not push directly to `main`.
    ```bash
    git checkout -b feature/amazing-new-feature
    # or
    git checkout -b fix/bug-fix-name


### How Can You Contribute?

Reporting Bugs
If you find a bug, please create a New Issue on GitHub. Include:

A clear title and description.

Steps to reproduce the bug.

Screenshots (if applicable).

Suggesting Enhancements
Have an idea for the FIR Generator or the Legal Knowledge Base? Open an issue and tag it as enhancement. We love discussing new ideas!

### Pull Requests (PRs)
Code Style:
Python: Follow PEP 8 guidelines. Keep code clean and commented.

Frontend: Keep HTML and CSS classes organized (Tailwind CSS preferred).

Test Your Changes:

Ensure the backend starts without errors: uvicorn main:app --reload

Test the frontend flow (Analysis -> Results) to ensure the API connects correctly.

Submit:

Push your branch to GitHub.
Open a Pull Request against the main branch of this repository.
Describe your changes clearly in the PR description.

⚖️ Adding Legal Data:
One of the most valuable ways to contribute is by expanding our ipc_data.txt file.

If you add new sections, please follow the existing format:

Section [Number]: [Title]
[Description text...]
After adding data, run python ingest.py to verify that the vector database builds successfully.

### Code of Conduct
We are committed to providing a friendly, safe, and welcoming environment for all. Please be kind and respectful in your issues and pull request comments. Harassment or abusive behavior will not be tolerated.

Thank you for helping us democratize legal knowledge! 🇮🇳