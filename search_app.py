import os
import re
import math
import platform
import subprocess
import threading
import webbrowser
from flask import Flask, render_template_string, request, jsonify

# ==========================================
# 1. 配置区 (⚠️修改为你保存 markdown 的文件夹)
# ==========================================
TARGET_FOLDER = r"D:\create\code\search_text\test_data"
PORT = 5000

# ==========================================
# 2. 前端代码
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>我的 AI 知识库</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #f8f9fa; color: #333; }

        /* 顶部导航栏 */
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        h1 { margin: 0; color: #2c3e50; font-size: 24px; }

        /* 刷新按钮样式 */
        .refresh-btn { background: white; border: 1px solid #cbd5e0; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; color: #4a5568; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }
        .refresh-btn:hover { border-color: #4299e1; color: #4299e1; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .refresh-btn:active { transform: scale(0.98); }

        .search-container { position: sticky; top: 20px; background: #f8f9fa; padding-bottom: 20px; z-index: 100; }
        .search-box { width: 100%; padding: 16px; font-size: 18px; border: 2px solid #e9ecef; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); transition: all 0.3s; outline: none; }
        .search-box:focus { border-color: #4299e1; box-shadow: 0 0 0 4px rgba(66, 153, 225, 0.15); }

        .result-item { background: white; padding: 20px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); cursor: pointer; border-left: 4px solid transparent; transition: transform 0.2s; }
        .result-item:hover { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(0,0,0,0.08); border-left-color: #4299e1; }
        .result-title { font-size: 18px; font-weight: 600; color: #2d3748; margin-bottom: 8px; display: flex; justify-content: space-between; }
        .result-path { font-size: 12px; color: #a0aec0; font-family: monospace; background: #edf2f7; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }
        .result-snippet { font-size: 14px; color: #4a5568; line-height: 1.6; word-break: break-all; }
        .highlight { background-color: #fefcbf; color: #744210; font-weight: bold; padding: 0 2px; border-radius: 2px; }
        .score-tag { font-size: 12px; background: #c6f6d5; color: #22543d; padding: 2px 8px; border-radius: 12px; font-weight: normal; }

        /* Toast 提示 */
        #toast { visibility: hidden; min-width: 250px; background-color: #333; color: #fff; text-align: center; border-radius: 4px; padding: 16px; position: fixed; z-index: 1; left: 50%; bottom: 30px; transform: translateX(-50%); font-size: 14px; }
        #toast.show { visibility: visible; animation: fadein 0.5s, fadeout 0.5s 2.5s; }
        @keyframes fadein { from {bottom: 0; opacity: 0;} to {bottom: 30px; opacity: 1;} }
        @keyframes fadeout { from {bottom: 30px; opacity: 1;} to {bottom: 0; opacity: 0;} }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 AI Chat Archive</h1>
        <button class="refresh-btn" onclick="refreshIndex()">
            <span>🔄</span> 更新索引
        </button>
    </div>

    <div class="search-container">
        <input type="text" id="searchInput" class="search-box" placeholder="搜索 Markdown 笔记或 AI 对话..." autofocus>
    </div>
    <div id="results"></div>
    <div id="toast">索引已更新！</div>

    <script>
        const searchInput = document.getElementById('searchInput');
        const resultsDiv = document.getElementById('results');
        let debounceTimer;

        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => performSearch(e.target.value), 200);
        });

        async function performSearch(query) {
            if (!query.trim()) { resultsDiv.innerHTML = ''; return; }
            try {
                const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                renderResults(data, query);
            } catch (e) { console.error(e); }
        }

        // 新增：调用后端重建索引
        async function refreshIndex() {
            const btn = document.querySelector('.refresh-btn');
            const originalText = btn.innerHTML;
            btn.innerHTML = '⏳ 更新中...';

            try {
                const res = await fetch('/api/refresh');
                const data = await res.json();
                showToast(`更新完成！当前共 ${data.count} 个文档`);
                // 如果搜索框里有字，自动重新搜一下
                if (searchInput.value) performSearch(searchInput.value);
            } catch (e) {
                showToast('更新失败');
            } finally {
                btn.innerHTML = originalText;
            }
        }

        function showToast(message) {
            const x = document.getElementById("toast");
            x.innerText = message;
            x.className = "show";
            setTimeout(function(){ x.className = x.className.replace("show", ""); }, 3000);
        }

        function highlight(text, query) {
            if (!query) return text;
            const terms = query.split(/\s+/).filter(t => t);
            let html = text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;"); // 简单的 HTML 转义防止 markdown 标签破坏布局

            terms.forEach(term => {
                const regex = new RegExp(`(${term})`, 'gi');
                html = html.replace(regex, '<span class="highlight">$1</span>');
            });
            return html;
        }

        function renderResults(results, query) {
            if (results.length === 0) {
                resultsDiv.innerHTML = '<div style="text-align:center;color:#cbd5e0;margin-top:50px;">未找到相关文档</div>';
                return;
            }
            resultsDiv.innerHTML = results.map(item => `
                <div class="result-item" onclick="openFile('${item.path.replace(/\\\\/g, '\\\\\\\\')}')">
                    <div class="result-title">
                        ${highlight(item.title, query)}
                        <span class="score-tag">Score: ${item.score}</span>
                    </div>
                    <div class="result-path">${item.path}</div>
                    <div class="result-snippet">${highlight(item.snippet, query)}</div>
                </div>
            `).join('');
        }

        async function openFile(path) {
            await fetch(`/api/open?path=${encodeURIComponent(path)}`);
        }
    </script>
</body>
</html>
"""

# ==========================================
# 3. 后端逻辑
# ==========================================
app = Flask(__name__)

# 全局数据
inverted_index = {}
documents = {}
doc_count = 0


def tokenize(text):
    # 简单的分词
    return re.findall(r'[\u4e00-\u9fa5]|[a-zA-Z0-9]+', text.lower())


def build_index_logic():
    """ 独立的构建索引逻辑 """
    global doc_count, inverted_index, documents

    # 临时变量，防止构建过程中影响当前搜索
    new_index = {}
    new_docs = {}
    new_count = 0

    print(f"🔄 开始扫描: {TARGET_FOLDER} ...")
    for root, dirs, files in os.walk(TARGET_FOLDER):
        for file in files:
            if not file.lower().endswith(('.md', '.txt', '.py', '.json', '.html')):
                continue

            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                doc_id = new_count
                new_count += 1
                new_docs[doc_id] = {"id": doc_id, "title": file, "path": path, "content": content}

                tokens = tokenize(content)
                token_counts = {}
                for t in tokens: token_counts[t] = token_counts.get(t, 0) + 1

                for t, count in token_counts.items():
                    if t not in new_index: new_index[t] = {}
                    new_index[t][doc_id] = count
            except:
                pass

    # 原子替换全局变量
    inverted_index = new_index
    documents = new_docs
    doc_count = new_count
    print(f"✅ 索引构建完成! 文档数: {doc_count}")
    return doc_count


# --- 路由 ---

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/search')
def search_api():
    query = request.args.get('q', '')
    if not query: return jsonify([])

    tokens = tokenize(query)
    scores = {}

    for q_token in tokens:
        for idx_token, doc_map in inverted_index.items():
            match_weight = 0
            if idx_token == q_token:
                match_weight = 10
            elif q_token in idx_token:
                match_weight = 2

            if match_weight > 0:
                # +1 防止 doc_count 为 0
                idf = math.log10((doc_count + 1) / (len(doc_map) + 1)) + 1
                for doc_id, tf in doc_map.items():
                    scores[doc_id] = scores.get(doc_id, 0) + (tf * idf * match_weight)

    results = []
    for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:30]:
        doc = documents[doc_id]
        # 智能摘要：尝试找第一个关键词出现的位置
        snippet_idx = 0
        content_lower = doc['content'].lower()
        for t in tokens:
            idx = content_lower.find(t)
            if idx != -1:
                snippet_idx = idx
                break

        start = max(0, snippet_idx - 20)
        # 限制摘要长度
        snippet = doc['content'][start:start + 150]
        results.append(
            {"title": doc['title'], "path": doc['path'], "snippet": snippet + "...", "score": round(score, 2)})

    return jsonify(results)


@app.route('/api/refresh')
def refresh_api():
    """ 手动触发索引重建的接口 """
    count = build_index_logic()
    return jsonify({"status": "success", "count": count})


@app.route('/api/open')
def open_api():
    path = request.args.get('path')
    if path and os.path.exists(path):
        try:
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':
                subprocess.call(('open', path))
            else:
                subprocess.call(('xdg-open', path))
            return "OK"
        except:
            pass
    return "Not Found", 404


if __name__ == '__main__':
    # 启动时先建一次
    build_index_logic()

    threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    print(f"✨ 服务已启动: http://127.0.0.1:{PORT}")
    app.run(port=PORT)