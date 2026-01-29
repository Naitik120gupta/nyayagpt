# ⚖️ Nyay Sahayak

### Your AI-Powered Guide to Indian Criminal Law

**Nyay Sahayak** is an intelligent legal assistant designed to bridge the gap between complex legal jargon and the common man. Built using **Retrieval-Augmented Generation (RAG)**, it instantly maps real-world crime descriptions to the relevant sections of the **Indian Penal Code (IPC)** and helps users draft official **First Information Reports (FIR)**.

---

## 🚀 Key Features

* **🔍 Instant Legal Analysis:** Describe a crime in plain English (e.g., *"A man broke into my house at night and threatened me"*), and the AI identifies the applicable IPC sections (e.g., Section 446, Section 506).
* **🧠 RAG Architecture:** Unlike standard chatbots, Nyay Sahayak retrieves exact legal text from a verified knowledge base before generating answers, ensuring accuracy and reducing hallucinations.
* **📝 Guided FIR Generator:** A step-by-step wizard that helps users structure a formal police complaint (FIR) based on the incident analysis.
* **⚡ Modern Tech Stack:** Powered by Google's **Gemini API**, **ChromaDB** for vector search, and a fast **FastAPI** backend.

---

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, Uvicorn
* **AI & LLM:** Google Gemini API (`gemini-1.5-flash`, `embedding-001`)
* **Database:** ChromaDB (Vector Store)
* **Frontend:** HTML5, Tailwind CSS, Vanilla JavaScript

---

## ⚙️ Architecture

Nyay Sahayak uses a **Retrieval-Augmented Generation (RAG)** pipeline:
1.  **Ingestion:** The Indian Penal Code (IPC) text is embedded into vectors and stored in **ChromaDB**.
2.  **Retrieval:** User queries are converted to vectors; the system searches the database for the most relevant legal sections.
3.  **Generation:** The retrieved legal context + user query are sent to **Google Gemini**, which generates a fact-based analysis.

---

## 🏃‍♂️ Getting Started

Follow these steps to set up the project locally.

### Prerequisites
* Python 3.10+
* A Google Gemini API Key

### Installation

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/yourusername/nyay-sahayak.git](https://github.com/yourusername/nyay-sahayak.git)
    cd nyay-sahayak/backend
    ```

2.  **Set Up Virtual Environment**
    ```bash
    python -m venv venv
    # Windows:
    .\venv\Scripts\activate
    # Mac/Linux:
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**
    Create a `.env` file in the `backend` folder:
    ```env
    GEMINI_API_KEY="your_api_key_here"
    ```

5.  **Build the Knowledge Base**
    Run the ingestion script to create the vector database:
    ```bash
    python ingest.py
    ```

6.  **Run the Server**
    ```bash
    uvicorn main:app --reload
    ```

7.  **Launch the App**
    Open `frontend/index.html` in your browser.

---

## 🔮 Roadmap

* [ ] **Full Legal Database:** Integrate CrPC (Criminal Procedure Code) and Indian Evidence Act.
* [ ] **Multilingual Support:** Add Hindi and regional language support for wider accessibility.
* [ ] **Voice Input:** Allow users to describe incidents verbally.
* [ ] **Citation Library:** Link real-world case law judgments to analysis.

---

## 🤝 Contributing

Contributions are welcome! Please fork the repository and submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

### Disclaimer
*Nyay Sahayak is a prototype for educational and informational purposes. It does not constitute professional legal advice.*