import os
import re
import math
import platform
import subprocess
import threading
import webbrowser
import pickle
import time
import hashlib
import jieba  # 🟢 引入结巴分词
from flask import Flask, render_template_string, request, jsonify
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import Counter

# ==========================================
# 1. 配置区
# ==========================================
TARGET_FOLDER = r"D:\create\code\search_text\test_data"
PORT = 5000
INDEX_FILE = "search_index.pkl"

# ==========================================
# 2. 前端代码 (增加摘要高亮逻辑)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>智能本地知识库 (Jieba+BM25版)</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown-light.min.css">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body { font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #f4f6f8; color: #333; }
        .header { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center; }
        h1 { margin: 0; font-size: 22px; color: #2c3e50; }
        .status-badge { font-size: 12px; background: #e2e8f0; padding: 4px 8px; border-radius: 4px; color: #4a5568; }
        .watching-badge { background: #c6f6d5; color: #22543d; display: flex; align-items: center; gap: 5px; }
        .watching-badge::before { content: ''; width: 8px; height: 8px; background: #48bb78; border-radius: 50%; display: inline-block; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .search-box { width: 100%; padding: 18px; font-size: 18px; border: 2px solid transparent; border-radius: 12px; margin-top: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); outline: none; transition: 0.3s; }
        .search-box:focus { border-color: #4299e1; box-shadow: 0 0 0 4px rgba(66, 153, 225, 0.15); }
        .result-item { background: white; padding: 20px; border-radius: 10px; margin-top: 15px; cursor: pointer; transition: 0.2s; border-left: 4px solid transparent; }
        .result-item:hover { transform: translateY(-2px); border-left-color: #4299e1; box-shadow: 0 8px 16px rgba(0,0,0,0.08); }
        .result-title { font-size: 18px; font-weight: bold; color: #2d3748; margin-bottom: 5px; display: flex; justify-content: space-between; }
        .result-path { font-size: 12px; color: #a0aec0; font-family: monospace; background: #f7fafc; padding: 2px 6px; border-radius: 4px; }
        .result-snippet { margin-top: 8px; font-size: 14px; color: #4a5568; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
        .highlight { background: #fefcbf; color: #b7791f; font-weight: bold; padding: 0 2px; border-radius: 2px; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 999; backdrop-filter: blur(2px); }
        .modal-content { position: relative; margin: 2% auto; width: 90%; max-width: 1000px; height: 90%; background: white; border-radius: 12px; display: flex; flex-direction: column; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25); }
        .modal-header { padding: 15px 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; background: #fafafa; border-radius: 12px 12px 0 0; }
        .markdown-body { padding: 30px; overflow-y: auto; flex: 1; font-size: 16px; line-height: 1.8; }
        .btn { padding: 6px 12px; background: #edf2f7; border: 1px solid #cbd5e0; border-radius: 6px; cursor: pointer; font-size: 14px; transition: 0.2s; margin-left: 5px; }
        .btn:hover { background: #e2e8f0; border-color: #a0aec0; }
        .btn-primary { background: #4299e1; color: white; border-color: #3182ce; }
        .btn-primary:hover { background: #3182ce; }
        .btn-secondary { background: #fff; border-color: #cbd5e0; color: #4a5568; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 智能本地知识库</h1>
        <div style="display:flex; gap:10px;">
            <span class="status-badge watching-badge">Jieba分词已启用</span>
            <span class="status-badge" id="doc-count">文档: 0</span>
        </div>
    </div>
    <input type="text" id="searchInput" class="search-box" placeholder="试试搜索: '测试 报错' 或 'Python 教程'..." autofocus>
    <div id="results"></div>

    <div id="previewModal" class="modal" onclick="if(event.target===this)this.style.display='none'">
        <div class="modal-content">
            <div class="modal-header">
                <strong id="modalTitle" style="font-size: 18px;"></strong>
                <div style="display:flex; align-items:center;">
                    <button class="btn btn-primary" onclick="openCurrentFile(false)">🚀 默认打开</button>
                    <button class="btn btn-secondary" onclick="openCurrentFile(true)">📂 选择应用...</button>
                    <button class="btn" onclick="document.getElementById('previewModal').style.display='none'" style="margin-left: 15px;">❌</button>
                </div>
            </div>
            <div class="markdown-body" id="modalBody"></div>
        </div>
    </div>
    <script>
        const searchInput = document.getElementById('searchInput');
        const resultsDiv = document.getElementById('results');
        let currentPath = '';

        fetch('/api/status').then(r=>r.json()).then(d => { document.getElementById('doc-count').innerText = `文档: ${d.count}`; });

        searchInput.addEventListener('input', (e) => {
            const query = e.target.value;
            if(!query.trim()) { resultsDiv.innerHTML = ''; return; }
            fetch(`/api/search?q=${encodeURIComponent(query)}`).then(r => r.json()).then(data => renderResults(data, query));
        });

        function renderResults(results, query) {
            if (results.length === 0) { resultsDiv.innerHTML = '<div style="text-align:center; padding:20px; color:#999">🔍 没找到相关内容</div>'; return; }
            resultsDiv.innerHTML = results.map(item => `
                <div class="result-item">
                    <div class="result-title" onclick="showPreview('${item.path.replace(/\\\\/g, '\\\\\\\\')}', '${item.title}')">
                        ${highlight(item.title, query)}
                        <span style="font-size:12px; font-weight:normal; color:#aaa">BM25: ${item.score.toFixed(2)}</span>
                    </div>
                    <div class="result-path">${item.path}</div>
                    <div class="result-snippet">${highlight(item.snippet, query)}</div>
                </div>
            `).join('');
        }

        // 简单的分词高亮逻辑，这里为了前端性能简单切分，主要高亮靠后端返回的snippet
        function highlight(text, query) {
            if(!text) return "";
            if(!query) return text;
            // 前端做简单高亮
            let html = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
            // 把query拆成字或词
            const terms = query.split(/[\s\.,，。]+/).filter(t=>t);
            terms.forEach(term => { 
                if(term.length > 0){
                    const regex = new RegExp(`(${term})`, 'gi'); 
                    html = html.replace(regex, '<span class="highlight">$1</span>'); 
                }
            });
            return html;
        }

        async function showPreview(path, title) {
            currentPath = path;
            const modal = document.getElementById('previewModal');
            const body = document.getElementById('modalBody');
            document.getElementById('modalTitle').innerText = title;
            modal.style.display = 'block';
            body.innerHTML = '<div style="text-align:center; color:#666; margin-top:50px;">正在加载...</div>';
            const res = await fetch(`/api/content?path=${encodeURIComponent(path)}`);
            const data = await res.json();
            body.innerHTML = data.content ? marked.parse(data.content) : '<p style="color:red">❌ 文件读取失败</p>';
        }

        function openCurrentFile(force) { if(currentPath) fetch(`/api/open?path=${encodeURIComponent(currentPath)}&force=${force}`); }
    </script>
</body>
</html>
"""

# ==========================================
# 3. 后端逻辑
# ==========================================
app = Flask(__name__)

inverted_index = {}
documents = {}
file_hashes = {}
doc_count = 0
index_lock = threading.Lock()


def calculate_md5(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()


# 🟢 进化：使用 Jieba 搜索引擎模式分词
def tokenize(text):
    # cut_for_search 会把 "长江大桥" 分成 "长江", "大桥", "长江大桥"
    # 非常适合搜索倒排索引
    if not text: return []
    words = jieba.cut_for_search(text.lower())
    # 过滤掉空格、换行和标点符号 (保留中文和英文单词)
    filtered = [w.strip() for w in words if w.strip() and len(w.strip()) > 0]
    return filtered


def save_index():
    with index_lock:
        try:
            with open(INDEX_FILE, 'wb') as f:
                pickle.dump({"inverted_index": inverted_index, "documents": documents, "doc_count": doc_count,
                             "file_hashes": file_hashes}, f)
        except Exception as e:
            print(f"❌ 保存失败: {e}")


def load_index():
    global inverted_index, documents, doc_count, file_hashes
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, 'rb') as f:
                data = pickle.load(f)
                inverted_index = data.get("inverted_index", {})
                documents = data.get("documents", {})
                doc_count = data.get("doc_count", 0)
                file_hashes = data.get("file_hashes", {})
            print(f"📂 索引加载成功: {doc_count} 个文档 (Jieba模式)。")
            return True
        except:
            print("⚠️ 索引版本不兼容，将重新构建。")
    return False


def remove_file_from_index(path):
    global doc_count
    with index_lock:
        target_id = next((did for did, doc in documents.items() if doc['path'] == path), None)
        if target_id is None: return
        print(f"🗑️ 移除: {os.path.basename(path)}")
        del documents[target_id]
        if path in file_hashes: del file_hashes[path]
        doc_count = len(documents)
        for term in inverted_index:
            if target_id in inverted_index[term]: del inverted_index[term][target_id]
        save_index()


def add_file_to_index(path):
    global doc_count
    filename = os.path.basename(path)
    if filename.startswith(('~', '$', '.')) or not filename.lower().endswith(
            ('.txt', '.md', '.py', '.json', '.js', '.c', '.cpp', '.java')):
        return

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        new_hash = calculate_md5(content)
        if path in file_hashes and file_hashes[path] == new_hash: return

        print(f"🔄 Jieba 索引中: {filename}")
        file_hashes[path] = new_hash

        with index_lock:
            existing_id = next((did for did, doc in documents.items() if doc['path'] == path), None)
            doc_id = existing_id if existing_id is not None else max(documents.keys(), default=0) + 1

            # 使用 Jieba 分词
            tokens = tokenize(content)
            title_tokens = tokenize(filename)
            all_tokens = title_tokens * 5 + tokens  # 标题权重加倍

            documents[doc_id] = {
                "id": doc_id,
                "title": filename,
                "path": path,
                "content": content,
                "length": len(all_tokens)
            }

            token_counts = Counter(all_tokens)
            for t, count in token_counts.items():
                if t not in inverted_index: inverted_index[t] = {}
                inverted_index[t][doc_id] = count

        save_index()
    except FileNotFoundError:
        remove_file_from_index(path)
    except Exception as e:
        print(f"❌ 读取失败 {path}: {e}")


# --- 智能摘要算法 ---
def get_smart_snippet(content, query_tokens, window_size=150):
    """
    找到所有关键词出现的位置，选择最密集的一个窗口作为摘要。
    """
    content_lower = content.lower()
    matches = []

    # 1. 找到所有 token 在文本中的位置
    for token in query_tokens:
        if not token: continue
        start = 0
        while True:
            idx = content_lower.find(token, start)
            if idx == -1: break
            matches.append(idx)
            start = idx + 1

    if not matches:
        return content[:window_size] + "..."  # 没找到（可能是标题匹配），返回开头

    matches.sort()

    # 2. 滑动窗口算法：找包含 match 最多的窗口
    best_start = 0
    max_score = 0

    # 如果匹配点很少，直接取第一个
    if len(matches) < 2:
        start_pos = max(0, matches[0] - 30)
        return content[start_pos: start_pos + window_size] + "..."

    # 扫描
    for i in range(len(matches)):
        # 窗口结束位置
        end_pos = matches[i] + window_size
        score = 0
        # 看这个窗口里包住了多少个 match
        for j in range(i, len(matches)):
            if matches[j] < end_pos:
                score += 1
            else:
                break

        if score > max_score:
            max_score = score
            best_start = max(0, matches[i] - 20)  # 稍微往前一点，保留上下文

    return content[best_start: best_start + window_size] + "..."


class FileChangeHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory: add_file_to_index(event.src_path)

    def on_modified(self, event):
        if not event.is_directory: add_file_to_index(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory: remove_file_from_index(event.src_path)


def start_watching():
    observer = Observer()
    observer.schedule(FileChangeHandler(), TARGET_FOLDER, recursive=True)
    observer.start()
    return observer


def initial_scan_and_clean():
    print("🚀 初始化 Jieba 分词引擎... (第一次可能稍慢)")
    # 预热 Jieba
    jieba.initialize()

    actual_files = set()
    for root, dirs, files in os.walk(TARGET_FOLDER):
        for file in files:
            full_path = os.path.join(root, file)
            add_file_to_index(full_path)
            actual_files.add(full_path)
    with index_lock:
        for did, doc in list(documents.items()):
            if doc['path'] not in actual_files: remove_file_from_index(doc['path'])


# --- 搜索接口 (BM25 + Jieba + 智能摘要) ---
@app.route('/api/search')
def search():
    query = request.args.get('q', '').strip()
    if not query: return jsonify([])

    # 使用 jieba 切分搜索词
    tokens = tokenize(query)
    if not tokens: return jsonify([])  # 只有标点符号情况

    scores = {}
    k1 = 1.5
    b = 0.75
    N = len(documents)

    total_length = sum(doc.get('length', 0) for doc in documents.values())
    # 🟢 修复：除以零保护
    avg_dl = (total_length / N) if N > 0 and total_length > 0 else 1

    for q_token in tokens:
        matching_docs_map = {}
        for idx_token, doc_map in inverted_index.items():
            # 模糊匹配：因为 jieba cut_for_search 已经把词拆得很细了，这里可以用 in
            # 但要小心性能。优化：只检查包含关系的
            if q_token in idx_token or idx_token in q_token:
                for doc_id, freq in doc_map.items():
                    matching_docs_map[doc_id] = matching_docs_map.get(doc_id, 0) + freq

        n_q = len(matching_docs_map)
        if n_q == 0: continue

        idf = math.log((N - n_q + 0.5) / (n_q + 0.5) + 1)

        for doc_id, freq in matching_docs_map.items():
            if doc_id not in documents: continue
            doc_len = documents[doc_id].get('length', 1)
            numerator = freq * (k1 + 1)
            denominator = freq + k1 * (1 - b + b * (doc_len / avg_dl))
            scores[doc_id] = scores.get(doc_id, 0) + idf * (numerator / denominator)

    results = []
    for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:20]:
        doc = documents[doc_id]
        # 🟢 进化：使用智能摘要
        snippet = get_smart_snippet(doc['content'], tokens)
        results.append({
            "title": doc['title'],
            "path": doc['path'],
            "score": score,
            "snippet": snippet
        })
    return jsonify(results)


@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)


@app.route('/api/status')
def status(): return jsonify({"count": len(documents)})


@app.route('/api/content')
def get_content():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        if path: remove_file_from_index(path)
        return jsonify({"content": None})
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return jsonify({"content": f.read(50000)})
    except:
        return jsonify({"content": None})


@app.route('/api/open')
def open_file():
    path = request.args.get('path')
    force_select = request.args.get('force') == 'true'
    if path and os.path.exists(path):
        if platform.system() == 'Windows':
            if force_select:
                subprocess.Popen(['rundll32', 'shell32.dll,OpenAs_RunDLL', path])
            else:
                try:
                    os.startfile(path)
                except:
                    subprocess.Popen(['rundll32', 'shell32.dll,OpenAs_RunDLL', path])
        else:
            cmd = 'open' if platform.system() == 'Darwin' else 'xdg-open'
            subprocess.call((cmd, path))
    return "OK"


if __name__ == '__main__':
    load_index()
    initial_scan_and_clean()
    observer = start_watching()
    threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    try:
        app.run(port=PORT, debug=False)
    finally:
        observer.stop(); observer.join()