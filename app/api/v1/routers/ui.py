"""UI router for serving the web interface."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui", tags=["ui"])


@router.get("/", response_class=HTMLResponse)
async def view_responses_ui() -> str:
    """Serve the responses viewer UI."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Responses Viewer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .controls {
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        .controls input, .controls select, .controls button {
            padding: 10px 15px;
            border: 1px solid #ced4da;
            border-radius: 6px;
            font-size: 14px;
        }
        .controls input {
            flex: 1;
            min-width: 200px;
        }
        .controls select {
            min-width: 150px;
        }
        .controls button {
            background: #667eea;
            color: white;
            border: none;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.3s;
        }
        .controls button:hover {
            background: #5568d3;
        }
        .stats {
            padding: 20px;
            background: #f8f9fa;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            border-bottom: 1px solid #dee2e6;
        }
        .stat-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            color: #6c757d;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        .stat-card .value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        .responses {
            padding: 20px;
        }
        .response-card {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .response-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .response-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #dee2e6;
        }
        .provider-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
            text-transform: uppercase;
        }
        .provider-openai { background: #10a37f; color: white; }
        .provider-gemini { background: #4285f4; color: white; }
        .provider-groq { background: #ff6b6b; color: white; }
        .provider-huggingface { background: #ffd93d; color: #333; }
        .provider-mock { background: #95a5a6; color: white; }
        .metrics {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .metric {
            display: flex;
            flex-direction: column;
        }
        .metric-label {
            font-size: 12px;
            color: #6c757d;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }
        .prompt {
            background: white;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            border-left: 4px solid #667eea;
        }
        .response-text {
            background: white;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 300px;
            overflow-y: auto;
        }
        .error {
            background: #fee;
            color: #c33;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #c33;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        .empty {
            text-align: center;
            padding: 60px;
            color: #6c757d;
        }
        .timestamp {
            color: #6c757d;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 LLM Responses Viewer</h1>
            <p>View and analyze responses from multiple AI providers</p>
        </div>
        
        <div class="controls">
            <input type="text" id="requestIdFilter" placeholder="Filter by Request ID (optional)">
            <select id="providerFilter">
                <option value="">All Providers</option>
                <option value="openai">OpenAI</option>
                <option value="gemini">Gemini</option>
                <option value="groq">Groq</option>
                <option value="huggingface">Hugging Face</option>
                <option value="mock">Mock</option>
            </select>
            <button onclick="loadResponses()">🔍 Load Responses</button>
            <button onclick="loadStats()">📊 Refresh Stats</button>
        </div>
        
        <div class="stats" id="stats">
            <div class="stat-card">
                <h3>Total Responses</h3>
                <div class="value" id="totalResponses">-</div>
            </div>
            <div class="stat-card">
                <h3>Total Requests</h3>
                <div class="value" id="totalRequests">-</div>
            </div>
            <div class="stat-card">
                <h3>Success Rate</h3>
                <div class="value" id="successRate">-</div>
            </div>
            <div class="stat-card">
                <h3>Avg Latency</h3>
                <div class="value" id="avgLatency">-</div>
            </div>
        </div>
        
        <div class="responses" id="responses">
            <div class="loading">Loading responses...</div>
        </div>
    </div>
    
    <script>
        const API_BASE = '/api/v1/responses';
        
        async function loadStats() {
            try {
                const response = await fetch(`${API_BASE}/stats`);
                const data = await response.json();
                
                document.getElementById('totalResponses').textContent = data.total_responses || 0;
                document.getElementById('totalRequests').textContent = data.total_requests || 0;
                
                const successRate = data.total_responses > 0 
                    ? ((data.successful_responses / data.total_responses) * 100).toFixed(1) + '%'
                    : '0%';
                document.getElementById('successRate').textContent = successRate;
                
                const avgLatency = data.average_latency_ms 
                    ? (data.average_latency_ms / 1000).toFixed(2) + 's'
                    : '0s';
                document.getElementById('avgLatency').textContent = avgLatency;
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        }
        
        async function loadResponses() {
            const requestId = document.getElementById('requestIdFilter').value.trim();
            const provider = document.getElementById('providerFilter').value;
            
            const params = new URLSearchParams();
            if (requestId) params.append('request_id', requestId);
            if (provider) params.append('provider', provider);
            params.append('limit', '50');
            
            document.getElementById('responses').innerHTML = '<div class="loading">Loading responses...</div>';
            
            try {
                const response = await fetch(`${API_BASE}/?${params.toString()}`);
                const data = await response.json();
                
                if (data.responses.length === 0) {
                    document.getElementById('responses').innerHTML = 
                        '<div class="empty">No responses found. Try adjusting your filters.</div>';
                    return;
                }
                
                document.getElementById('responses').innerHTML = data.responses.map(r => `
                    <div class="response-card">
                        <div class="response-header">
                            <div>
                                <span class="provider-badge provider-${r.provider}">${r.provider}</span>
                                <span class="timestamp" style="margin-left: 15px;">${new Date(r.created_at).toLocaleString()}</span>
                            </div>
                            <div class="metrics">
                                <div class="metric">
                                    <div class="metric-label">Latency</div>
                                    <div class="metric-value">${(r.latency_ms / 1000).toFixed(2)}s</div>
                                </div>
                                <div class="metric">
                                    <div class="metric-label">Tokens</div>
                                    <div class="metric-value">${r.total_tokens}</div>
                                </div>
                            </div>
                        </div>
                        <div class="prompt">
                            <strong>Prompt:</strong> ${escapeHtml(r.prompt.substring(0, 200))}${r.prompt.length > 200 ? '...' : ''}
                        </div>
                        ${r.error ? `
                            <div class="error">
                                <strong>Error:</strong> ${escapeHtml(r.error)}
                            </div>
                        ` : `
                            <div class="response-text">${escapeHtml(r.raw_response)}</div>
                        `}
                        <div style="margin-top: 10px; font-size: 12px; color: #6c757d;">
                            Request ID: <code>${r.request_id}</code>
                            ${r.prompt_tokens ? ` | Prompt: ${r.prompt_tokens} tokens` : ''}
                            ${r.completion_tokens ? ` | Completion: ${r.completion_tokens} tokens` : ''}
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                document.getElementById('responses').innerHTML = 
                    `<div class="error">Failed to load responses: ${error.message}</div>`;
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Load on page load
        window.addEventListener('load', () => {
            loadStats();
            loadResponses();
        });
        
        // Allow Enter key to trigger search
        document.getElementById('requestIdFilter').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') loadResponses();
        });
    </script>
</body>
</html>
    """

