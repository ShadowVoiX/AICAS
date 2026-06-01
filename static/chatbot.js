let quizQuestions = [];
let currentQuizIndex = 0;
let recentToolsCache = [];

function toggleChat() {
    const overlay = document.getElementById("chatOverlay");
    overlay.classList.toggle("active");

    if (overlay.classList.contains("active")) {
        scrollChatToBottom();
    }
}
function toggleExpand() {
    const overlay = document.getElementById("chatOverlay");
    const btn = document.getElementById("expandBtn");

    overlay.classList.toggle("expanded");

    if (overlay.classList.contains("expanded")) {
        btn.innerHTML = "🗗"; // collapse icon
    } else {
        btn.innerHTML = "⛶"; // expand icon
    }
}

function saveChatMessage(text, type) {
    let chatHistory = JSON.parse(sessionStorage.getItem("chatHistory")) || [];

    chatHistory.push({
        text: text,
        type: type
    });

    sessionStorage.setItem("chatHistory", JSON.stringify(chatHistory));
}

function loadChatHistory() {
    const chatBody = document.getElementById("chatBody");
    const chatHistory = JSON.parse(sessionStorage.getItem("chatHistory")) || [];

    chatBody.innerHTML = "";

    if (chatHistory.length === 0) {
        chatBody.innerHTML = `<p class="bot-msg msg">Hi! How can I help you?</p>`;
        scrollChatToBottom();
        return;
    }

    chatHistory.forEach(msg => {
        addMessage(msg.text, msg.type, false);
    });

    scrollChatToBottom();
}

function scrollChatToBottom() {
    const chatBody = document.getElementById("chatBody");

    requestAnimationFrame(() => {
        chatBody.scrollTop = chatBody.scrollHeight;
    });
}

function clearChat() {
    sessionStorage.removeItem("chatHistory");

    document.getElementById("chatBody").innerHTML =
        `<p class="bot-msg">Chat cleared. How can I help you?</p>`;
}

function addMessage(text, type, save = true) {
    const chatBody = document.getElementById("chatBody");

    const div = document.createElement("div");
    div.classList.add("msg");

    if (type === "user") {
        div.classList.add("user-msg");
    } else {
        div.classList.add("bot-msg");
    }

    div.innerHTML = text;

    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;

    if (save) {
        saveChatMessage(text, type);
    }
}

async function sendMessage() {

    const input = document.getElementById("chatInput");
    const chatFile = document.getElementById("chatFile");
    const selectedFile = document.getElementById("selectedFile");

    const message = input.value.trim();
    const file = chatFile.files[0];

    if (!message && !file) return;

    let displayMessage = message;

    if (file) {
        displayMessage += ` 📎 ${file.name}`;
    }

    addMessage(displayMessage, "user");

    const uid = localStorage.getItem("uid");


    const formData = new FormData();
    formData.append("message", message);
    formData.append("uid", uid);

    if (file) {
        formData.append("file", file);
    }

    chatFile.value = "";
    selectedFile.innerHTML = "";

    input.value = "";

    const response = await fetch("/chatbot", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    chatFile.value = "";
    selectedFile.innerHTML = "";

    if (data.type === "text") {
        addMessage(data.reply, "bot");
    }

    else if (data.type === "timetable") {
        let html = `
            <b>Your Timetable</b><br><br>
            <table style="width:100%; border-collapse: collapse; font-size: 12px;">
                <tr>
                    <th>Code</th>
                    <th>Name</th>
                    <th>Day</th>
                    <th>Time</th>
                    <th>Venue</th>
                </tr>
        `;

        data.data.forEach(c => {
            html += `
                <tr>
                    <td>${c.code}</td>
                    <td>${c.name}</td>
                    <td>${c.day}</td>
                    <td>${c.time}</td>
                    <td>${c.venue}</td>
                </tr>
            `;
        });

        html += `</table>`;
        addMessage(html, "bot");
    }
    else if (data.type === "exam_timetable") {
        let html = `
        <b>Your Final Exam Timetable</b><br><br>
        <table style="width:100%; border-collapse: collapse; font-size: 12px;">
            <tr>
                <th>Code</th>
                <th>Date</th>
                <th>Day</th>
                <th>Time</th>
                <th>Status</th>
            </tr>
    `;

        data.data.forEach(e => {
            html += `
            <tr>
                <td>${e.code}</td>
                <td>${e.date ? e.date : "-"}</td>
                <td>${e.day ? e.day : "-"}</td>
                <td>${e.time ? e.time : "-"}</td>
                <td>${e.status}</td>
            </tr>
        `;
        });

        html += `</table>`;
        addMessage(html, "bot");
    }

    else if (data.type === "redirect") {
        addMessage(data.reply, "bot");

        setTimeout(() => {
            window.location.href = data.url;
        }, 800);
    }

    else {
        addMessage("I do not understand", "bot");
    }
    await saveCurrentChatToFirebase();
}
function makeResizable(resizer, targetPane, side) {
    let isDragging = false;

    resizer.addEventListener("mousedown", () => {
        isDragging = true;
        document.body.style.cursor = "col-resize";
    });

    document.addEventListener("mousemove", (e) => {
        if (!isDragging) return;

        const layout = document.querySelector(".chat-layout");
        const layoutRect = layout.getBoundingClientRect();

        if (side === "left") {
            let newWidth = e.clientX - layoutRect.left;

            if (newWidth < 160) newWidth = 160;
            if (newWidth > 420) newWidth = 420;

            targetPane.style.width = newWidth + "px";
        }

        if (side === "right") {
            let newWidth = layoutRect.right - e.clientX;

            if (newWidth < 180) newWidth = 180;
            if (newWidth > 460) newWidth = 460;

            targetPane.style.width = newWidth + "px";
        }
    });

    document.addEventListener("mouseup", () => {
        isDragging = false;
        document.body.style.cursor = "default";
    });
}
window.addEventListener("load", () => {
    loadChatHistory();
    loadChatHistoryList();
    loadRecentTools();

    const left = document.querySelector(".chat-left");
    const right = document.querySelector(".chat-right");

    const resizerLeft = document.getElementById("resizer-left");
    const resizerRight = document.getElementById("resizer-right");

    makeResizable(resizerLeft, left, "left");
    makeResizable(resizerRight, right, "right");
});
document.getElementById("chatInput").addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
    }
});

const chatFile = document.getElementById("chatFile");
const selectedFile = document.getElementById("selectedFile");

chatFile.addEventListener("change", function () {

    selectedFile.innerHTML = "";

    if (this.files.length > 0) {

        const bubble = document.createElement("div");
        bubble.classList.add("file-bubble");

        bubble.innerHTML = `
            <span>${this.files[0].name}</span>
            <button class="remove-file">✕</button>
        `;

        selectedFile.appendChild(bubble);

        // remove file
        bubble.querySelector(".remove-file").addEventListener("click", () => {

            chatFile.value = "";

            selectedFile.innerHTML = "";
        });
    }
});
async function generateQuiz() {

    const input = document.getElementById("chatInput");
    const chatFile = document.getElementById("chatFile");
    const rightPanel = document.querySelector(".chat-right");

    const file = chatFile.files[0];
    const uid = localStorage.getItem("uid");


    if (!file) {
        alert("Please choose a PDF or TXT file first.");
        return;
    }

    rightPanel.style.width = "420px";
    rightPanel.style.minWidth = "420px";

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="quiz-container">
            <h2>Generating Quiz...</h2>
            <p>Please wait while AICAS reads your file.</p>
        </div>
    `;

    const formData = new FormData();
    formData.append("uid", uid);
    formData.append("file", file);

    const response = await fetch("/generate-quiz", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    if (data.status !== "success") {
        rightPanel.innerHTML = `
            <div class="quiz-container">
                <h2>Quiz failed</h2>
                <p>${data.message}</p>
            </div>
        `;
        return;
    }
    await saveGeneratedTool("Quiz", "Generated Quiz", data.quiz);

    quizQuestions = JSON.parse(data.quiz);
    currentQuizIndex = 0;
    window.quizCorrectCount = 0;

    clearSelectedFile();
    renderQuizQuestion();
}
function renderQuizQuestion() {
    const rightPanel = document.querySelector(".chat-right");
    const q = quizQuestions[currentQuizIndex];

    rightPanel.innerHTML = `
        <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="quiz-container">
            <div class="quiz-header">
                <h2>Generated Quiz</h2>
                <p>Based on uploaded file</p>
            </div>

            <div class="quiz-progress">
                ${currentQuizIndex + 1} / ${quizQuestions.length}
            </div>

            <div class="quiz-question">
                ${q.question}
            </div>

            <div class="quiz-options">
                ${q.options.map((option, index) => `
                    <button class="quiz-option" onclick="checkQuizAnswer(this, ${index})">
                        ${String.fromCharCode(65 + index)}. ${option}
                    </button>
                `).join("")}
            </div>

            <div class="quiz-footer">
                <button class="next-btn" onclick="nextQuizQuestion()">
                    Next
                </button>
            </div>
        </div>
    `;
}
function nextQuizQuestion() {

    if (currentQuizIndex < quizQuestions.length - 1) {

        currentQuizIndex++;
        renderQuizQuestion();

    } else {

        const total = quizQuestions.length;

        const correct = window.quizCorrectCount || 0;
        const wrong = total - correct;

        const percent = Math.round((correct / total) * 100);

        document.querySelector(".chat-right").innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>

    <div class="quiz-result-container">
        <h1 class="quiz-complete-title">
            You did it! Quiz Complete.
        </h1>

        <div class="quiz-result-card">
            <div class="quiz-circle-wrapper">
                <div class="quiz-circle"
                    style="background:
                    conic-gradient(
                        #38b44a ${percent}%,
                        #f1f1f1 ${percent}%
                    );">

                    <div class="quiz-circle-inner">
                        <h2>${correct}/${total}</h2>
                        <p>${percent}%</p>
                    </div>
                </div>
            </div>

            <div class="quiz-result-stats">
                <div class="quiz-stat-row">
                    <span>Right</span>
                    <span class="correct-text">${correct}</span>
                </div>

                <div class="quiz-stat-row">
                    <span>Wrong</span>
                    <span class="wrong-text">${wrong}</span>
                </div>
            </div>
        </div>

        <button class="next-btn" onclick="restartQuiz()">
            Restart Quiz
        </button>
    </div>
`;
    }
}
function restartQuiz() {
    currentQuizIndex = 0;
    window.quizCorrectCount = 0;
    renderQuizQuestion();
}
function checkQuizAnswer(button, selectedIndex) {

    const q = quizQuestions[currentQuizIndex];
    const options = document.querySelectorAll(".quiz-option");

    options.forEach(opt => {
        opt.disabled = true;
    });

    if (!window.quizCorrectCount)
        window.quizCorrectCount = 0;

    // CORRECT ANSWER
    options[q.correctIndex].classList.add("quiz-correct");

    // USER CHOSE CORRECT
    if (selectedIndex === q.correctIndex) {

        window.quizCorrectCount++;

        button.innerHTML += `
            <div class="quiz-explain">
                ✓ Correct. ${q.explanation}
            </div>
        `;
    }

    // USER CHOSE WRONG
    else {

        button.classList.add("quiz-wrong");

        button.innerHTML += `
            <div class="quiz-explain">
                ✗ ${q.explanation}
            </div>
        `;
    }
}
let flashcards = [];
let currentFlashcardIndex = 0;
let showingAnswer = false;

async function generateFlashcards() {
    const chatFile = document.getElementById("chatFile");
    const rightPanel = document.querySelector(".chat-right");

    const file = chatFile.files[0];
    const uid = localStorage.getItem("uid");

    if (!file) {
        alert("Please choose a PDF or TXT file first.");
        return;
    }

    rightPanel.style.width = "420px";
    rightPanel.style.minWidth = "420px";

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="flashcard-container">
            <h2>Generating Flashcards...</h2>
            <p>Please wait while AICAS reads your file.</p>
        </div>
    `;

    const formData = new FormData();
    formData.append("uid", uid);
    formData.append("file", file);

    const response = await fetch("/generate-flashcards", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    if (data.status !== "success") {
        rightPanel.innerHTML = `
            <div class="flashcard-container">
                <h2>Flashcards failed</h2>
                <p>${data.message}</p>
            </div>
        `;
        return;
    }
    await saveGeneratedTool("Flashcards", "Generated Flashcards", data.flashcards);

    flashcards = JSON.parse(data.flashcards);
    currentFlashcardIndex = 0;
    showingAnswer = false;

    clearSelectedFile();
    renderFlashcard();
}

function renderFlashcard() {
    const rightPanel = document.querySelector(".chat-right");
    const card = flashcards[currentFlashcardIndex];

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="flashcard-container">
            <h2>Generated Flashcards</h2>
            <p>${currentFlashcardIndex + 1} / ${flashcards.length}</p>

            <div class="flashcard-card">
                <div class="flashcard-label">
                    ${showingAnswer ? "Answer" : "Question"}
                </div>

                <div class="flashcard-text">
                    ${showingAnswer ? card.answer : card.question}
                </div>
            </div>

            <div class="flashcard-actions">
                <button onclick="flipFlashcard()">Flip</button>
                <button onclick="nextFlashcard()">Next</button>
            </div>
        </div>
    `;
}

function flipFlashcard() {
    showingAnswer = !showingAnswer;
    renderFlashcard();
}

function nextFlashcard() {
    if (currentFlashcardIndex < flashcards.length - 1) {
        currentFlashcardIndex++;
    } else {
        currentFlashcardIndex = 0;
    }

    showingAnswer = false;
    renderFlashcard();
}
async function generateSummary() {
    const chatFile = document.getElementById("chatFile");
    const rightPanel = document.querySelector(".chat-right");

    const file = chatFile.files[0];
    const uid = localStorage.getItem("uid");

    if (!file) {
        alert("Please choose a PDF or TXT file first.");
        return;
    }

    rightPanel.style.width = "420px";
    rightPanel.style.minWidth = "420px";

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="summary-container">
            <h2>Generating Summary...</h2>
            <p>Please wait while AICAS reads your file.</p>
        </div>
    `;

    const formData = new FormData();
    formData.append("uid", uid);
    formData.append("file", file);

    const response = await fetch("/generate-summary", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    if (data.status !== "success") {
        rightPanel.innerHTML = `
        <button class="back-btn" onclick="showToolHome()">← Back</button>
            <div class="summary-container">
                <h2>Summary failed</h2>
                <p>${data.message}</p>
            </div>
        `;
        return;
    }
    await saveGeneratedTool("Summary", "Generated Summary", data.summary);

    clearSelectedFile();
    renderSummary(data.summary);
}

function renderSummary(summaryText) {
    const rightPanel = document.querySelector(".chat-right");

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="summary-container">
            <h2>Notes Summary</h2>

            <div class="summary-card">
                ${summaryText.replace(/\n/g, "<br>")}
            </div>
        </div>
    `;
}
function openStudyPlanForm() {
    const rightPanel = document.querySelector(".chat-right");

    rightPanel.style.width = "420px";
    rightPanel.style.minWidth = "420px";

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="study-container">
            <h2>Study Plan Generator</h2>
            <p>Fill in your study details.</p>

            <div class="study-form">
                <input type="text" id="studySubject" placeholder="Subject name e.g. Software Testing">
                <input type="date" id="examDate">
                <input type="number" id="chapterCount" placeholder="Number of chapters">
                <input type="number" id="studyHours" placeholder="Study hours per day">
                <textarea id="studyTopics" placeholder="Topics or chapters, optional"></textarea>

                <button onclick="generateStudyPlan()">Generate Plan</button>
            </div>
        </div>
    `;
}

async function generateStudyPlan() {
    const subject = document.getElementById("studySubject").value.trim();
    const examDate = document.getElementById("examDate").value;
    const chapterCount = document.getElementById("chapterCount").value;
    const studyHours = document.getElementById("studyHours").value;
    const topics = document.getElementById("studyTopics").value.trim();

    const rightPanel = document.querySelector(".chat-right");

    if (!subject || !examDate || !chapterCount || !studyHours) {
        alert("Please fill in subject, exam date, chapters, and study hours.");
        return;
    }

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="study-container">
            <h2>Generating Study Plan...</h2>
            <p>Please wait while AICAS prepares your revision schedule.</p>
        </div>
    `;

    const response = await fetch("/generate-study-plan", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            subject: subject,
            examDate: examDate,
            chapterCount: chapterCount,
            studyHours: studyHours,
            topics: topics
        })
    });

    const data = await response.json();

    if (data.status !== "success") {
        rightPanel.innerHTML = `
        <button class="back-btn" onclick="showToolHome()">← Back</button>
            <div class="study-container">
                <h2>Study Plan failed</h2>
                <p>${data.message}</p>
            </div>
        `;
        return;
    }

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="study-container">
            <h2>Your Study Plan</h2>

            <div class="study-card">
                ${data.studyPlan.replace(/\n/g, "<br>")}
            </div>

            <br>

            <button onclick="openStudyPlanForm()">Create Another Plan</button>
        </div>
    `;
}
async function generateKeyTerms() {
    const chatFile = document.getElementById("chatFile");
    const rightPanel = document.querySelector(".chat-right");

    const file = chatFile.files[0];
    const uid = localStorage.getItem("uid");

    if (!file) {
        alert("Please choose a PDF or TXT file first.");
        return;
    }

    rightPanel.style.width = "420px";
    rightPanel.style.minWidth = "420px";

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="keyterm-container">
            <h2>Extracting Key Terms...</h2>
            <p>Please wait while AICAS reads your file.</p>
        </div>
    `;

    const formData = new FormData();
    formData.append("uid", uid);
    formData.append("file", file);

    const response = await fetch("/generate-keyterms", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    if (data.status !== "success") {
        rightPanel.innerHTML = `
        <button class="back-btn" onclick="showToolHome()">← Back</button>
            <div class="keyterm-container">
                <h2>Key Terms failed</h2>
                <p>${data.message}</p>
            </div>
        `;
        return;
    }
    await saveGeneratedTool("Key Terms", "Generated Key Terms", data.keyTerms);

    const keyTerms = JSON.parse(data.keyTerms);
    clearSelectedFile();
    renderKeyTerms(keyTerms);
}

function renderKeyTerms(keyTerms) {
    const rightPanel = document.querySelector(".chat-right");

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="keyterm-container">
            <h2>Key Terms</h2>
            <p>Important terms extracted from your notes.</p>

            <div class="keyterm-list">
                ${keyTerms.map(item => `
                    <div class="keyterm-card">
                        <h3>${item.term}</h3>
                        <p>${item.definition}</p>
                    </div>
                `).join("")}
            </div>
        </div>
    `;
}
async function explainBeginner() {

    const chatFile = document.getElementById("chatFile");
    const rightPanel = document.querySelector(".chat-right");

    const file = chatFile.files[0];
    const uid = localStorage.getItem("uid");


    if (!file) {
        alert("Please choose a PDF or TXT file first.");
        return;
    }

    rightPanel.style.width = "420px";
    rightPanel.style.minWidth = "420px";

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="beginner-container">
            <h2>Reading Notes...</h2>
            <p>AICAS is simplifying the material.</p>
        </div>
    `;

    const formData = new FormData();

    formData.append("uid", uid);
    formData.append("file", file);

    const response = await fetch("/explain-beginner", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    if (data.status !== "success") {

        rightPanel.innerHTML = `
            <h2>Failed</h2>
            <p>${data.message}</p>
        `;

        return;
    }
    await saveGeneratedTool("Beginner", "Beginner Explanation", data.explanation);
    clearSelectedFile();

    rightPanel.innerHTML = `
    <button class="back-btn" onclick="showToolHome()">← Back</button>
        <div class="beginner-container">

            <h2>Explain Like I'm a Beginner</h2>

            <div class="beginner-card">
                ${data.explanation.replace(/\n/g, "<br>")}
            </div>

        </div>
    `;
}
function showToolHome() {
    const rightPanel = document.querySelector(".chat-right");
    rightPanel.style.width = "260px";
    rightPanel.style.minWidth = "";

    rightPanel.innerHTML = `
        <div id="toolHome">
            <div class="tool-grid">
                <button class="tool-btn" onclick="generateQuiz()">Quiz</button>
                <button class="tool-btn" onclick="generateFlashcards()">Flashcards</button>
                <button class="tool-btn" onclick="generateSummary()">Summary</button>
                <button class="tool-btn" onclick="openStudyPlanForm()">Study Plan</button>
                <button class="tool-btn" onclick="generateKeyTerms()">Key Terms</button>
                <button class="tool-btn" onclick="explainBeginner()">Beginner</button>
            </div>

            <hr class="tool-divider">

            <h3 class="recent-title">Recently Created</h3>
            <div id="recentToolsList" class="recent-tools-list"></div>
        </div>
    `;

    loadRecentTools();
}
async function saveGeneratedTool(type, title, content) {
    const uid = localStorage.getItem("uid");

    await fetch("/save-generated-tool", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            uid: uid,
            type: type,
            title: title,
            content: content
        })
    });

    loadRecentTools();
}
async function loadRecentTools() {
    const uid = localStorage.getItem("uid");
    const list = document.getElementById("recentToolsList");

    if (!uid || !list) return;

    const response = await fetch("/get-generated-tools", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ uid: uid })
    });

    const data = await response.json();

    if (data.status !== "success" || data.tools.length === 0) {
        list.innerHTML = `<p style="color:#94a3b8;font-size:13px;">No recent tools yet.</p>`;
        return;
    }

    recentToolsCache = data.tools;

    list.innerHTML = data.tools.map((tool, index) => `
        <div class="recent-item">

    <div class="recent-content"
         onclick="openGeneratedTool(${index})">

        <b>${tool.type}</b><br>
        <span>${tool.title}</span>

    </div>

    <button class="menu-btn"
            onclick="toggleToolMenu('${tool.id}')">
        ⋮
    </button>

    <div class="dropdown-menu"
         id="tool-menu-${tool.id}">
        <button onclick="deleteGeneratedTool('${tool.id}')">
            Delete
        </button>
    </div>

</div>
    `).join("");
}
function openGeneratedTool(index) {
    const tool = recentToolsCache[index];
    const rightPanel = document.querySelector(".chat-right");

    if (!tool) return;

    rightPanel.style.width = "420px";
    rightPanel.style.minWidth = "420px";

    if (tool.type === "Quiz") {
        quizQuestions = JSON.parse(tool.content);
        currentQuizIndex = 0;
        window.quizCorrectCount = 0;
        renderQuizQuestion();
        return;
    }

    if (tool.type === "Flashcards") {
        flashcards = JSON.parse(tool.content);
        currentFlashcardIndex = 0;
        showingAnswer = false;
        renderFlashcard();
        return;
    }

    if (tool.type === "Key Terms") {
        const keyTerms = JSON.parse(tool.content);
        renderKeyTerms(keyTerms);
        return;
    }

    if (tool.type === "Summary") {
        renderSummary(tool.content);
        return;
    }

    if (tool.type === "Study Plan") {
        renderStudyPlan(tool.content);
        return;
    }

    if (tool.type === "Beginner") {
        renderBeginner(tool.content);
        return;
    }
}
function renderStudyPlan(studyPlanText) {
    const rightPanel = document.querySelector(".chat-right");

    rightPanel.innerHTML = `
        <button class="back-btn" onclick="showToolHome()">← Back</button>

        <div class="study-container">
            <h2>Your Study Plan</h2>

            <div class="study-card">
                ${studyPlanText.replace(/\n/g, "<br>")}
            </div>
        </div>
    `;
}
function renderBeginner(explanationText) {
    const rightPanel = document.querySelector(".chat-right");

    rightPanel.innerHTML = `
        <button class="back-btn" onclick="showToolHome()">← Back</button>

        <div class="beginner-container">
            <h2>Explain Like I'm a Beginner</h2>

            <div class="beginner-card">
                ${explanationText.replace(/\n/g, "<br>")}
            </div>
        </div>
    `;
}
let currentHistoryId = null;

async function saveCurrentChatToFirebase() {
    const uid = localStorage.getItem("uid");
    const messages = JSON.parse(sessionStorage.getItem("chatHistory")) || [];

    if (!uid || messages.length === 0) return;

    const firstUserMessage = messages.find(m => m.type === "user");
    const title = firstUserMessage
        ? firstUserMessage.text.substring(0, 30)
        : "New Chat";

    const response = await fetch("/save-chat-history", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            uid: uid,
            historyId: currentHistoryId,
            title: title,
            messages: messages
        })
    });

    const data = await response.json();

    if (data.status === "success") {
        currentHistoryId = data.historyId;
        loadChatHistoryList();
    }
}

async function loadChatHistoryList() {
    const uid = localStorage.getItem("uid");
    const list = document.getElementById("chatHistoryList");

    if (!uid || !list) return;

    const response = await fetch("/get-chat-histories", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ uid: uid })
    });

    const data = await response.json();

    if (data.status !== "success" || data.histories.length === 0) {
        list.innerHTML = `<p style="color:#94a3b8;font-size:13px;">No chat history yet.</p>`;
        return;
    }

    list.innerHTML = data.histories.map(chat => `
    <div class="history-item">

        <div class="history-title-text"
             onclick="openChatHistory('${chat.id}')">
            ${chat.title}
        </div>

        <button class="menu-btn"
                onclick="toggleHistoryMenu('${chat.id}')">
            ⋮
        </button>

        <div class="dropdown-menu"
             id="history-menu-${chat.id}">
            <button onclick="deleteHistory('${chat.id}')">
                Delete
            </button>
        </div>

    </div>
`).join("");
}

async function openChatHistory(historyId) {
    const uid = localStorage.getItem("uid");

    const response = await fetch("/get-chat-history", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            uid: uid,
            historyId: historyId
        })
    });

    const data = await response.json();

    if (data.status !== "success") return;

    currentHistoryId = historyId;

    sessionStorage.setItem(
        "chatHistory",
        JSON.stringify(data.history.messages)
    );

    loadChatHistory();
}

function startNewChat() {
    currentHistoryId = null;
    sessionStorage.removeItem("chatHistory");

    document.getElementById("chatBody").innerHTML =
        `<p class="bot-msg msg">Hi! How can I help you?</p>`;
}
function toggleHistoryMenu(id) {

    const menu =
        document.getElementById(`history-menu-${id}`);

    menu.style.display =
        menu.style.display === "block"
            ? "none"
            : "block";
}

function toggleToolMenu(id) {

    const menu =
        document.getElementById(`tool-menu-${id}`);

    menu.style.display =
        menu.style.display === "block"
            ? "none"
            : "block";
}
async function deleteHistory(historyId) {

    const uid =
        localStorage.getItem("uid");

    await fetch("/delete-history", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            uid: uid,
            historyId: historyId
        })
    });

    loadChatHistoryList();
}
async function deleteGeneratedTool(toolId) {

    const uid =
        localStorage.getItem("uid");

    await fetch("/delete-generated-tool", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            uid: uid,
            toolId: toolId
        })
    });

    loadRecentTools();
}
function clearSelectedFile() {
    document.getElementById("chatFile").value = "";
    document.getElementById("selectedFile").innerHTML = "";
}