// State
let allFolders = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchFolders();
    checkConnection();
    updateStats();

    // Listen for category changes to update experience levels
    document.getElementById('category').addEventListener('change', updateExperienceLevels);
});

// Fetch Brevo Folders for the dropdown
async function fetchFolders() {
    try {
        const response = await fetch('/api/folders');
        const data = await response.json();
        allFolders = data;

        const select = document.getElementById('category');
        select.innerHTML = '<option value="">All Categories</option>';
        // Count name occurrences to handle duplicates
        const counts = {};
        data.forEach(f => counts[f.name] = (counts[f.name] || 0) + 1);

        data.forEach(folder => {
            const option = document.createElement('option');
            option.value = folder.id;

            // Show the number of lists to help distinguish folders
            const listInfo = folder.list_count !== undefined ? ` (${folder.list_count} lists)` : '';
            option.textContent = `${folder.name}${listInfo}`;
            select.appendChild(option);
        });
    } catch (error) {
        log("Error fetching folders: " + error);
    }
}

// Check API Connectivity
async function checkConnection() {
    const dot = document.getElementById('api-status-dot');
    const text = document.getElementById('api-status-text');

    dot.style.backgroundColor = '#f1e05a'; // Yellow
    text.textContent = 'Checking...';

    try {
        const response = await fetch('/api/validate');
        const data = await response.json();

        if (data.success) {
            dot.style.backgroundColor = '#2ea44f'; // Green
            text.textContent = 'API Connected';
        } else {
            dot.style.backgroundColor = '#da3633'; // Red
            text.textContent = 'Connection Error';
        }
        log(data.logs);
    } catch (error) {
        dot.style.backgroundColor = '#da3633';
        text.textContent = 'Server Offline';
    }
}

// Dry Run
async function runDryRun() {
    const params = getFormParams();
    if (!params.campaign_id) {
        alert("🚨 Campaign ID is required!\n\nThis ID prevents sending duplicates. Use the same ID to finish a list later.");
        log("❌ Error: Campaign ID missing");
        return;
    }
    log("\n>> Starting Dry Run for: " + (params.category || "All Categories") + "...");

    try {
        const response = await fetch('/api/dry-run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        const data = await response.json();
        log(data.logs);
    } catch (error) {
        log("Error: " + error);
    }
}

// Live Send (Opens Modal)
function runSend() {
    const campaignId = document.getElementById('campaign_id').value;
    if (!campaignId) {
        alert("🚨 Campaign ID is required!\n\nThis ID prevents sending duplicates. Use the same ID to finish a list later.");
        log("❌ Error: Campaign ID missing");
        return;
    }
    document.getElementById('confirm-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('confirm-modal').style.display = 'none';
}

async function confirmAndSend() {
    closeModal();
    const params = getFormParams();
    params.confirm = true;

    log("\n>> 🚀 STARTING LIVE CAMPAIGN: " + (params.campaign_id || "Auto-ID") + "...");

    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';

    try {
        const response = await fetch('/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        const data = await response.json();
        log(data.logs);
        updateStats();
    } catch (error) {
        log("Error: " + error);
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send Messages';
    }
}

// Analytics Summary
async function updateStats() {
    try {
        const response = await fetch('/api/summary');
        const data = await response.json();

        document.getElementById('stat-success').textContent = data.success;
        document.getElementById('stat-failed').textContent = data.failed;
        document.getElementById('stat-total').textContent = data.total;
        document.getElementById('stat-limit').textContent = data.limit;
    } catch (error) {
        console.error("Stats update failed", error);
    }
}

// Helpers
function getFormParams() {
    return {
        category: document.getElementById('category').value,
        experience: document.getElementById('experience').value,
        campaign_id: document.getElementById('campaign_id').value,
        job_title: document.getElementById('job_title').value,
        company: document.getElementById('company').value,
        location: document.getElementById('location').value,
        apply_link: document.getElementById('apply_link').value
    };
}

function log(text) {
    const output = document.getElementById('log-output');
    if (!text) return;
    output.textContent += "\n" + text;
    output.scrollTop = output.scrollHeight;
}

function clearLogs() {
    document.getElementById('log-output').textContent = "";
}

async function updateExperienceLevels() {
    const folder = document.getElementById('category').value;
    const select = document.getElementById('experience');

    if (!folder) {
        select.innerHTML = '<option value="all">Select Category First</option>';
        return;
    }

    select.innerHTML = '<option value="">Checking levels...</option>';

    try {
        const response = await fetch(`/api/folder-levels?folder=${encodeURIComponent(folder)}`);
        const levels = await response.json();

        select.innerHTML = '<option value="all">All Available Levels</option>';
        if (levels.length === 0) {
            select.innerHTML = '<option value="">No levels found in folder</option>';
        } else {
            levels.forEach(level => {
                const option = document.createElement('option');
                option.value = level;
                option.textContent = level; // Use exact name from Brevo
                select.appendChild(option);
            });
        }
    } catch (error) {
        log("Error updating levels: " + error);
    }
}

function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    document.getElementById(tabId + '-tab').classList.add('active');
    event.currentTarget.classList.add('active');
}
