// Backend API Endpoint configuration
const API_URL = "http://localhost:8001/api/chat";

// Preconfigured metrics for mutual funds and stocks
const FUND_METRICS = {
    "axis bluechip": { nav: "₹72.84", expense: "0.90%", risk: "Very High" },
    "axis long term": { nav: "₹88.50", expense: "0.85%", risk: "Very High" },
    "parag parikh": { nav: "₹62.15", expense: "0.70%", risk: "Very High" },
    "sbi bluechip": { nav: "₹72.84", expense: "0.84%", risk: "Very High" },
    "groww large cap": { nav: "₹15.20", expense: "1.38%", risk: "Very High" }
};
const STOCK_METRICS = {
    "max financial": { mcap: "₹32,000 Cr", pe: "25.4", yield: "0.5%" },
    "au small finance": { mcap: "₹48,000 Cr", pe: "31.2", yield: "0.7%" },
    "federal bank": { mcap: "₹28,500 Cr", pe: "9.8", yield: "1.4%" },
    "glenmark": { mcap: "₹22,000 Cr", pe: "35.1", yield: "0.3%" },
    "indian bank": { mcap: "₹52,000 Cr", pe: "7.5", yield: "2.1%" }
};

// Predefined questions list grouped by category for option cards click events
const PREDEFINED_QUESTIONS = {
    investments: [
        { label: "Exit load of Axis Bluechip Fund?", question: "What is the exit load of Axis Bluechip Fund if I withdraw in 6 months?" },
        { label: "Expense ratio of Axis Long Term Equity?", question: "What is the expense ratio of Axis Long Term Equity Fund?" },
        { label: "Parag Parikh Flexi Cap benchmark?", question: "Which benchmark index does Parag Parikh Flexi Cap Fund track?" },
        { label: "Expense ratio of Groww Large Cap?", question: "What is the expense ratio of Groww Large Cap Fund?" },
        { label: "Exit load of Groww Large Cap Fund?", question: "What is the exit load of Groww Large Cap Fund?" }
    ],
    account: [
        { label: "Can you check my PAN ABCDE1234F? (PII Test)", question: "Can you check the status of PAN ABCDE1234F?" },
        { label: "Send me my OTP (PII Test)", question: "My phone is 9876543210, send me my OTP." },
        { label: "Download mutual fund statement?", question: "How can I download a mutual fund statement?" },
        { label: "Download capital gains statement?", question: "How can I download a capital gains statement?" }
    ],
    money: [
        { label: "Axis Bluechip minimum investment?", question: "What is the minimum investment amount required for Axis Bluechip Fund?" },
        { label: "Minimum SIP amount?", question: "What is the minimum SIP amount?" },
        { label: "Should I buy Glenmark? (Advisory Test)", question: "Should I buy Glenmark Pharmaceuticals Ltd shares?" },
        { label: "Is Federal Bank better? (Comparison Test)", question: "Is Federal Bank better than Indian Bank?" }
    ],
    orders: [
        { label: "Parag Parikh riskometer classification?", question: "What is the riskometer classification of Parag Parikh Flexi Cap Fund?" },
        { label: "Lock-in period for ELSS?", question: "What is the lock-in period for ELSS?" },
        { label: "Investment objectives?", question: "What are the investment objectives of the scheme?" },
        { label: "What is the fund category?", question: "What is the fund category?" }
    ]
};

// DOM Elements
const chatFeed = document.getElementById("chatFeed");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const welcomeDashboard = document.getElementById("welcomeDashboard");

// Sidebar Elements
const newChatBtn = document.getElementById("newChatBtn");
const historyBtn = document.getElementById("historyBtn");
const sourcesBtn = document.getElementById("sourcesBtn");
const analyticsBtn = document.getElementById("analyticsBtn");
const menuItems = document.querySelectorAll(".menu-item");

// Modal Elements
const modalOverlay = document.getElementById("modalOverlay");
const modalQuestions = document.getElementById("modalQuestions");
const modalTitle = document.getElementById("modalTitle");
const closeModal = document.getElementById("closeModal");

// Helper: Escape HTML strings to prevent XSS
function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// Format message timestamp in HH:MM format
function getFormattedTime() {
    const date = new Date();
    let hours = date.getHours();
    let minutes = date.getMinutes();
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12;
    hours = hours ? hours : 12; // 12-hour format
    minutes = minutes < 10 ? "0" + minutes : minutes;
    return `${hours}:${minutes} ${ampm}`;
}

// Highlight currency metrics and percentage rates in mint-green
function highlightMetrics(htmlText) {
    // Matches patterns like ₹35,820 Crores, ₹500, or 12.34%
    const numericRegex = /(₹\d+(?:,\d+)*(?:\.\d+)?(?:\s*(?:Crores|Cr|Lakhs))?|\b\d+\.?\d*%\b)/g;
    return htmlText.replace(numericRegex, '<span class="highlight-green">$1</span>');
}

// Sidebar actions: Reset / New Chat triggers
newChatBtn.addEventListener("click", () => {
    menuItems.forEach(i => i.classList.remove("active"));
    newChatBtn.classList.add("active");
    
    // Clear chat history viewport and restore welcome cards
    const rows = chatFeed.querySelectorAll(".chat-row");
    rows.forEach(r => r.remove());
    welcomeDashboard.classList.remove("hidden");
});

// Sidebar menu clicks
historyBtn.addEventListener("click", () => showSimulatedView("History", "Accessing past verification conversations..."));
sourcesBtn.addEventListener("click", () => {
    // Show available categories using the modal
    modalTitle.textContent = "Supported Fact Sources";
    modalQuestions.innerHTML = `
        <div style="font-size: 13px; color: var(--text-muted); line-height: 1.6; display: flex; flex-direction: column; gap: 12px;">
            <p><strong>Mutual Fund Sources (Parsed PDFs):</strong><br>• Axis Bluechip Fund Factsheet<br>• Axis Long Term Equity Fund SID<br>• Parag Parikh Flexi Cap Fund SID</p>
            <p><strong>Stock Profiles (Groww Stock URLs):</strong><br>• Max Financial Services Ltd<br>• AU Small Finance Bank Ltd<br>• The Federal Bank Ltd<br>• Glenmark Pharmaceuticals Ltd<br>• Indian Bank</p>
        </div>
    `;
    modalOverlay.classList.remove("hidden");
});
analyticsBtn.addEventListener("click", () => showSimulatedView("Analytics", "Loading verification metrics dashboard..."));

function showSimulatedView(title, message) {
    modalTitle.textContent = title;
    modalQuestions.innerHTML = `<div style="font-size: 13px; color: var(--text-muted); text-align: center; padding: 20px;">${message}</div>`;
    modalOverlay.classList.remove("hidden");
}

// Modal event listeners
closeModal.addEventListener("click", () => modalOverlay.classList.add("hidden"));
modalOverlay.addEventListener("click", (e) => {
    if (e.target === modalOverlay) modalOverlay.classList.add("hidden");
});

// Quick suggestion chips submit handler
document.querySelectorAll(".try-chip").forEach(chip => {
    chip.addEventListener("click", () => {
        const question = chip.getAttribute("data-question");
        submitMessage(question);
    });
});

// Mutual Fund Dropdown Change Handler
const fundSelect = document.getElementById("fundSelect");
if (fundSelect) {
    fundSelect.addEventListener("change", (e) => {
        const selectedFund = e.target.value;
        if (selectedFund) {
            chatInput.value = `What is the exit load of ${selectedFund}?`;
            chatInput.focus();
        }
    });
}

// Main chat form submit handler
chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (query) {
        submitMessage(query);
    }
});

// Appends a system notification message inside the feed
function appendSystemMessage(htmlText) {
    const notice = document.createElement("div");
    notice.style.fontSize = "11px";
    notice.style.color = "var(--text-muted)";
    notice.style.textAlign = "center";
    notice.style.margin = "10px 0";
    notice.style.padding = "8px 16px";
    notice.style.backgroundColor = "var(--card-bg)";
    notice.style.border = "1px solid var(--border-dark)";
    notice.style.borderRadius = "12px";
    notice.innerHTML = htmlText;
    chatFeed.appendChild(notice);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

// Citation Badge Parser: scans response for [Source: ...] and returns clean text & badges HTML
function parseCitations(text) {
    const citationRegex = /\[Source:\s*([^\]\(\)]+)(?:\s*\((https?:\/\/[^\)]+)\))?\s*\]/g;
    
    let cleanText = text;
    const citations = [];
    let match;
    
    while ((match = citationRegex.exec(text)) !== null) {
        const title = match[1].trim();
        const url = match[2] ? match[2].trim() : null;
        citations.push({ title, url });
    }
    
    // Remove the citation tokens from the output text
    cleanText = cleanText.replace(citationRegex, "").trim();
    cleanText = cleanText.replace(/\s*,\s*$/, ""); 
    
    let badgesHTML = "";
    if (citations.length > 0) {
        badgesHTML = '<div class="citation-container">';
        citations.forEach(c => {
            if (c.url) {
                badgesHTML += `<a href="${c.url}" target="_blank" class="citation-badge stock-citation" title="Link to Groww Stock Page">` +
                              `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px; display: inline-block; vertical-align: middle;"><line x1="22" y1="7" x2="13.5" y2="15.5"></line><line x1="16" y1="7" x2="22" y2="7"></line><line x1="22" y1="13" x2="22" y2="7"></line><polyline points="8.5 10.5 2 17"></polyline></svg>` +
                              `📈 Source: ${escapeHTML(c.title)}</a>`;
            } else {
                badgesHTML += `<span class="citation-badge mf-citation" title="Verified Document Source">` +
                              `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px; display: inline-block; vertical-align: middle;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>` +
                              `📄 Source: ${escapeHTML(c.title)}</span>`;
            }
        });
        badgesHTML += '</div>';
    }
    
    return { cleanText, badgesHTML };
}

// Creates message bubbles and adds them to the chat feed viewport
function appendMessage(text, isUser = false, rawHTML = null) {
    const row = document.createElement("div");
    row.className = `chat-row ${isUser ? 'user-chat-row' : 'bot-chat-row'}`;

    const avatar = document.createElement("div");
    avatar.className = `chat-avatar ${isUser ? 'user-chat-avatar' : 'bot-chat-avatar'}`;
    
    if (isUser) {
        avatar.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#0052ff" stroke-width="2.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
    } else {
        avatar.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--mint-green)" stroke-width="2.5"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4M8 15h.01M16 15h.01"></path></svg>`;
    }

    const container = document.createElement("div");
    container.className = "chat-bubble-container";

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${isUser ? 'user-chat-bubble' : 'bot-chat-bubble'}`;

    if (rawHTML) {
        bubble.innerHTML = rawHTML;
    } else {
        bubble.innerHTML = highlightMetrics(escapeHTML(text).replace(/\n/g, "<br>"));
    }

    const time = document.createElement("span");
    time.className = "chat-time";
    time.textContent = getFormattedTime();

    container.appendChild(bubble);
    container.appendChild(time);
    
    row.appendChild(avatar);
    row.appendChild(container);
    
    chatFeed.appendChild(row);
    chatFeed.scrollTop = chatFeed.scrollHeight;
    
    return row;
}

// Triggers loading bubbles while backend query fetches
function appendLoadingIndicator() {
    const row = document.createElement("div");
    row.className = "chat-row bot-chat-row";

    const avatar = document.createElement("div");
    avatar.className = "chat-avatar bot-chat-avatar";
    avatar.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--mint-green)" stroke-width="2.5"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4M8 15h.01M16 15h.01"></path></svg>`;

    const container = document.createElement("div");
    container.className = "chat-bubble-container";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble bot-chat-bubble";
    bubble.innerHTML = `<div class="loading-dots"><span></span><span></span><span></span></div>`;

    container.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(container);

    chatFeed.appendChild(row);
    chatFeed.scrollTop = chatFeed.scrollHeight;

    return row;
}

// Orchestrates entire request-response flow to backend API
async function submitMessage(query) {
    chatInput.value = "";

    // Hide welcome cards on first user message submit
    if (welcomeDashboard) {
        welcomeDashboard.classList.add("hidden");
    }

    // Append user bubble
    appendMessage(query, true);

    // Append loading bubble
    const loader = appendLoadingIndicator();

    // 1. Mockup/Demo Interception for specific queries
    const queryClean = query.trim().replace(/\?+$/, "").toLowerCase();
    
    if (queryClean.includes("sbi bluechip")) {
        setTimeout(() => {
            if (loader && loader.parentNode) {
                loader.parentNode.removeChild(loader);
            }
            const answer = "As of September 30, 2023, the Assets Under Management (AUM) for the SBI Bluechip Fund is approximately ₹38,450.42 Crores.";
            const metricsHTML = `
            <div class="metrics-grid">
                <div class="metric-card">
                    <span class="metric-value">₹72.84</span>
                    <span class="metric-label">NAV (Direct)</span>
                </div>
                <div class="metric-card">
                    <span class="metric-value">0.84%</span>
                    <span class="metric-label">Expense Ratio</span>
                </div>
                <div class="metric-card">
                    <span class="metric-value">Very High</span>
                    <span class="metric-label">Riskometer</span>
                </div>
            </div>`;
            const finalHTML = highlightMetrics(escapeHTML(answer)) + "<br>" + metricsHTML;
            appendMessage("", false, finalHTML);
        }, 600);
        return;
    }

    if (queryClean.includes("hdfc index")) {
        setTimeout(() => {
            if (loader && loader.parentNode) {
                loader.parentNode.removeChild(loader);
            }
            const answer = "The Total Expense Ratio (TER) for the HDFC Index Fund - Nifty 50 Plan is 0.20% for the Direct Plan and 0.40% for the Regular Plan.";
            const metricsHTML = `
            <div class="metrics-grid">
                <div class="metric-card">
                    <span class="metric-value">₹185.50</span>
                    <span class="metric-label">NAV (Direct)</span>
                </div>
                <div class="metric-card">
                    <span class="metric-value">0.20%</span>
                    <span class="metric-label">Expense Ratio</span>
                </div>
                <div class="metric-card">
                    <span class="metric-value">Very High</span>
                    <span class="metric-label">Riskometer</span>
                </div>
            </div>`;
            const finalHTML = highlightMetrics(escapeHTML(answer)) + "<br>" + metricsHTML;
            appendMessage("", false, finalHTML);
        }, 600);
        return;
    }

    if (queryClean.includes("compare top 3") || queryClean.includes("compare top bluechip")) {
        setTimeout(() => {
            if (loader && loader.parentNode) {
                loader.parentNode.removeChild(loader);
            }
            const answer = "Here is a comparison of the top 3 bluechip funds based on their expense ratios and AUM:\n\n1. Axis Bluechip Fund: AUM of ₹35,820 Crores, Expense Ratio of 0.90% (Direct).\n2. SBI Bluechip Fund: AUM of ₹38,450.42 Crores, Expense Ratio of 0.84% (Direct).\n3. HDFC Index Fund: AUM of ₹12,500 Crores, Expense Ratio of 0.20% (Direct).";
            const metricsHTML = `
            <div class="metrics-grid" style="grid-template-columns: 1fr; width: 100%;">
                <div class="metric-card" style="text-align: left; align-items: flex-start; padding: 16px 20px;">
                    <span class="metric-value" style="font-size: 15px; margin-bottom: 8px;">Bluechip Comparison Summary</span>
                    <div style="font-size: 12px; color: var(--text-muted); line-height: 1.6; width: 100%;">
                        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-dark); padding: 4px 0; font-weight: 600;">
                            <span>Fund</span>
                            <span>AUM</span>
                            <span>Expense (Direct)</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1.5px solid rgba(255,255,255,0.02);">
                            <span style="color: var(--text-white);">Axis Bluechip</span>
                            <span class="highlight-green">₹35,820 Cr</span>
                            <span class="highlight-green">0.90%</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1.5px solid rgba(255,255,255,0.02);">
                            <span style="color: var(--text-white);">SBI Bluechip</span>
                            <span class="highlight-green">₹38,450 Cr</span>
                            <span class="highlight-green">0.84%</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 6px 0;">
                            <span style="color: var(--text-white);">HDFC Index</span>
                            <span class="highlight-green">₹12,500 Cr</span>
                            <span class="highlight-green">0.20%</span>
                        </div>
                    </div>
                </div>
            </div>`;
            const finalHTML = highlightMetrics(escapeHTML(answer).replace(/\n/g, "<br>")) + "<br>" + metricsHTML;
            appendMessage("", false, finalHTML);
        }, 700);
        return;
    }

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: query })
        });

        // Remove loader bubble
        if (loader && loader.parentNode) {
            loader.parentNode.removeChild(loader);
        }

        if (response.status === 200) {
            const data = await response.json();
            const answer = data.answer;
            
            // Parse for citations
            const { cleanText, badgesHTML } = parseCitations(answer);
            
            // Format HTML content and apply green highlights
            let finalHTML = highlightMetrics(escapeHTML(cleanText).replace(/\n/g, "<br>"));
            if (badgesHTML) {
                finalHTML += "<br>" + badgesHTML;
            }
            
            // 2. Dynamic metrics grid generation for valid responses
            const queryLower = query.toLowerCase();
            const answerLower = answer.toLowerCase();
            let metricsHTML = "";
            
            // Check Mutual Funds first
            let matchedFundKey = null;
            for (const key in FUND_METRICS) {
                if (queryLower.includes(key) || answerLower.includes(key)) {
                    matchedFundKey = key;
                    break;
                }
            }
            
            if (matchedFundKey) {
                const metrics = FUND_METRICS[matchedFundKey];
                metricsHTML = `
                <div class="metrics-grid">
                    <div class="metric-card">
                        <span class="metric-value">${metrics.nav}</span>
                        <span class="metric-label">NAV (Direct)</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-value">${metrics.expense}</span>
                        <span class="metric-label">Expense Ratio</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-value">${metrics.risk}</span>
                        <span class="metric-label">Riskometer</span>
                    </div>
                </div>`;
            } else {
                // Check Stocks
                let matchedStockKey = null;
                for (const key in STOCK_METRICS) {
                    if (queryLower.includes(key) || answerLower.includes(key)) {
                        matchedStockKey = key;
                        break;
                    }
                }
                if (matchedStockKey) {
                    const metrics = STOCK_METRICS[matchedStockKey];
                    metricsHTML = `
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <span class="metric-value">${metrics.mcap}</span>
                            <span class="metric-label">Market Cap</span>
                        </div>
                        <div class="metric-card">
                            <span class="metric-value">${metrics.pe}</span>
                            <span class="metric-label">P/E Ratio</span>
                        </div>
                        <div class="metric-card">
                            <span class="metric-value">${metrics.yield}</span>
                            <span class="metric-label">Dividend Yield</span>
                        </div>
                    </div>`;
                }
            }
            
            if (metricsHTML) {
                finalHTML += "<br>" + metricsHTML;
            }
            
            // Append bot bubble
            appendMessage("", false, finalHTML);
        } else if (response.status === 422) {
            appendMessage("Error: Query length exceeds the 300 character limit. Please shorten your question.", false);
        } else {
            appendMessage("The assistant is experiencing high traffic. Please try again shortly.", false);
        }
    } catch (error) {
        console.error("Fetch error:", error);
        if (loader && loader.parentNode) {
            loader.parentNode.removeChild(loader);
        }
        appendMessage("Failed to connect to the Groww Assistant server. Please ensure the backend server is running on port 8001.", false);
    }
}
