/**
 * HyGraph 前端逻辑
 */

(function () {
    "use strict";

    // ============================================================
    // 状态
    // ============================================================
    let currentGraph = { nodes: [], edges: [] };
    let currentTopic = "";
    let currentGraphId = null;      // 当前图谱在数据库里的 id（自动保存后获得）
    let expansionMap = {};
    let expansionCache = {};   // nodeId -> {nodes, edges}，收回的展开结果，再点开原样恢复
    let nodePositions = {};    // nodeId -> {x, y}，旧节点坐标，重渲染时固定不动
    const expandingNodes = new Set();  // 正在延伸中的节点 id，防止重复点击并发请求
    let activeNodeId = null;
    let chart = null;

    const edgeKey = (e) => `${e.source}→${e.target}→${e.label}`;


    // ============================================================
    // 初始化
    // ============================================================
    document.addEventListener("DOMContentLoaded", () => {
        const topicInput = document.getElementById("topicInput");
        const generateBtn = document.getElementById("generateBtn");
        const saveBtn = document.getElementById("saveBtn");
        const historyBtn = document.getElementById("historyBtn");
        const graphContainer = document.getElementById("graphChart");

        const chatInput = document.getElementById("chatInput");
        const sendBtn = document.getElementById("sendBtn");
        const chatMessages = document.getElementById("chatMessages");

        const historyModal = document.getElementById("historyModal");
        const closeHistoryBtn = document.getElementById("closeHistoryBtn");
        const historyList = document.getElementById("historyList");
        const exportPngBtn = document.getElementById("exportPngBtn");
        const exportJsonBtn = document.getElementById("exportJsonBtn");

        // ---- 事件绑定（先绑，不依赖 echarts） ----
        generateBtn.addEventListener("click", () => handleGenerate());
        topicInput.addEventListener("keydown", e => { if (e.key === "Enter") handleGenerate(); });
        saveBtn.addEventListener("click", () => handleSave());
        historyBtn.addEventListener("click", () => openHistory());
        closeHistoryBtn.addEventListener("click", () => closeHistory());
        historyModal.addEventListener("click", e => { if (e.target === historyModal) closeHistory(); });
        exportPngBtn.addEventListener("click", () => handleExportPng());
        exportJsonBtn.addEventListener("click", () => handleExportJson());
        sendBtn.addEventListener("click", () => handleChat());
        chatInput.addEventListener("keydown", e => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChat(); }
        });

        // ---- eCharts 本地加载（不依赖外部 CDN，断网/内网也能画图） ----
        const echartsScript = document.createElement("script");
        echartsScript.src = "/echarts.min.js";
        echartsScript.onload = () => {
            chart = echarts.init(graphContainer);
            window.addEventListener("resize", () => chart.resize());
            if (currentGraph) renderGraph();
        };
        echartsScript.onerror = () => chart = null;
        document.head.appendChild(echartsScript);


        // ============================================================
        // 生成图谱
        // ============================================================
        async function handleGenerate() {
            const topic = topicInput.value.trim();
            if (!topic) return alert("请输入一个知识主题");

            currentTopic = topic;
            currentGraph = { nodes: [], edges: [] };
            currentGraphId = null;
            expansionMap = {};
            expansionCache = {};
            nodePositions = {};
            activeNodeId = null;
            chatMessages.innerHTML = "";
            updateSaveBtn();

            generateBtn.disabled = true;
            generateBtn.textContent = "生成中...";
            chart?.showLoading({ text: "AI 正在分析构建知识图谱...", maskColor: "rgba(255,255,255,0.8)" });

            try {
                const res = await fetch("/api/graph/generate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ topic }),
                });
                const data = await res.json();
                if (!data.success) { alert(data.message); return; }
                currentGraph.nodes = data.graph.nodes;
                currentGraph.edges = data.graph.edges;
                updateSaveBtn();
                renderGraph();
                autoSaveGraph();   // 生成成功 → 静默自动入库
            } catch (err) {
                console.error(err);
                alert("网络错误，请确认后端已启动");
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = "生成知识图谱";
                chart?.hideLoading();
            }
        }


        // ============================================================
        // 展开 / 收回
        // ============================================================
        async function handleToggleNode(nodeId, nodeName) {
            if (expansionMap[nodeId]) {
                collapseNode(nodeId);
            } else {
                await expandNode(nodeId, nodeName);
            }
            updateSaveBtn();
        }

        function collapseNode(nodeId) {
            const exp = expansionMap[nodeId];
            if (!exp) return;
            for (const childId of exp.childNodeIds) {
                if (expansionMap[childId]) collapseNode(childId);
            }
            // 收回前先把这次的展开结果存进缓存，下次点开原样恢复（不再调 AI）
            expansionCache[nodeId] = {
                nodes: currentGraph.nodes.filter(n => exp.childNodeIds.has(n.id)),
                edges: currentGraph.edges.filter(e => exp.edgeKeys.has(edgeKey(e))),
            };
            currentGraph.nodes = currentGraph.nodes.filter(n => !exp.childNodeIds.has(n.id));
            // 删边要同时满足三个条件才不留下：
            // ①是本次展开引入的边  ②③起点/终点不是被删节点（清掉其他延伸跨连过来的悬空边）
            currentGraph.edges = currentGraph.edges.filter(
                e => !exp.edgeKeys.has(edgeKey(e))
                    && !exp.childNodeIds.has(e.source)
                    && !exp.childNodeIds.has(e.target)
            );
            delete expansionMap[nodeId];
            activeNodeId = null;
            renderGraph();
            syncSavedGraph();
        }

        // 把一批新节点/边合并进当前图谱（API 返回和缓存恢复共用这一套逻辑）
        function mergeExpansion(nodeId, newNodes, newEdges) {
            const existingIdSet = new Set(currentGraph.nodes.map(n => n.id));
            const existingEdgeSet = new Set(currentGraph.edges.map(e => edgeKey(e)));
            const childNodeIds = new Set();
            const edgeKeys = new Set();
            for (const node of newNodes) {
                if (!existingIdSet.has(node.id)) {
                    currentGraph.nodes.push(node);
                    existingIdSet.add(node.id);
                    childNodeIds.add(node.id);
                }
            }
            for (const edge of newEdges) {
                const key = edgeKey(edge);
                // 边的两端必须都在图谱里（防止悬空边），且不与已有边重复
                if (!existingEdgeSet.has(key) && existingIdSet.has(edge.source) && existingIdSet.has(edge.target)) {
                    currentGraph.edges.push(edge);
                    existingEdgeSet.add(key);
                    edgeKeys.add(key);
                }
            }
            expansionMap[nodeId] = { childNodeIds, edgeKeys };
        }

        // 从缓存恢复上次的展开结果
        function restoreExpansion(nodeId) {
            const cached = expansionCache[nodeId];
            if (!cached) return;
            mergeExpansion(nodeId, cached.nodes, cached.edges);
            delete expansionCache[nodeId];
        }

        async function expandNode(nodeId, nodeName) {
            // 正在延伸中的节点，重复点击直接忽略（否则并发请求会产生清不掉的孤儿节点）
            if (expandingNodes.has(nodeId)) return;
            activeNodeId = nodeId;

            // ① 展开过又收回的节点：直接从缓存恢复，秒开、不调 AI、结果和上次一样
            if (expansionCache[nodeId]) {
                restoreExpansion(nodeId);
                renderGraph();
                syncSavedGraph();
                return;
            }

            expandingNodes.add(nodeId);
            renderGraph();
            chart?.showLoading({ text: `正在探索「${nodeName}」的子节点...`, maskColor: "rgba(255,255,255,0.7)" });
            try {
                // 把已有节点的 id+name 都发给后端，AI 才能把新子节点和旧节点关联起来
                const existingNodes = currentGraph.nodes.map(n => ({ id: n.id, name: n.name }));
                const res = await fetch("/api/graph/expand", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ node_id: nodeId, node_name: nodeName, existing_nodes: existingNodes }),
                });
                const data = await res.json();
                if (!data.success) { activeNodeId = null; return; }
                mergeExpansion(nodeId, data.graph.nodes, data.graph.edges);
            } catch (err) {
                console.error("展开失败:", err);
            } finally {
                expandingNodes.delete(nodeId);
                chart?.hideLoading();
                renderGraph();
                syncSavedGraph();
            }
        }


        // ============================================================
        // 自动保存 / 自动同步（静默执行，失败不打扰用户）
        // ============================================================
        async function autoSaveGraph() {
            try {
                const res = await fetch("/api/graph/save", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ topic: currentTopic, graph: currentGraph }),
                });
                const data = await res.json();
                if (data.success) {
                    currentGraphId = data.id;
                    // 保存请求飞行期间用户可能又延伸/收回了，补一次同步让数据库收敛到最新
                    syncSavedGraph();
                }
            } catch (e) {
                console.warn("自动保存失败（不影响使用）:", e);
            }
        }

        // 延伸 / 收回 / 恢复后，把最新图谱覆盖同步到已保存的记录
        function syncSavedGraph() {
            if (!currentGraphId) return;
            fetch(`/api/graph/update/${currentGraphId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ graph: currentGraph }),
            }).catch(e => console.warn("自动同步失败（不影响使用）:", e));
        }


        // ============================================================
        // 保存图谱
        // ============================================================
        async function handleSave() {
            if (currentGraph.nodes.length === 0) return;
            saveBtn.disabled = true;
            saveBtn.textContent = "保存中...";
            try {
                let data;
                if (currentGraphId) {
                    // 已有自动保存的记录 → 覆盖更新，不产生重复
                    const res = await fetch(`/api/graph/update/${currentGraphId}`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ graph: currentGraph }),
                    });
                    data = await res.json();
                } else {
                    const res = await fetch("/api/graph/save", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ topic: currentTopic, graph: currentGraph }),
                    });
                    data = await res.json();
                    if (data.success) currentGraphId = data.id;
                }
                if (data.success) {
                    alert("已保存！（在「历史」里查看）");
                } else {
                    alert("保存失败");
                }
            } catch (err) {
                console.error(err);
                alert("保存失败，请重试");
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = "保存";
            }
        }


        // ============================================================
        // 历史记录
        // ============================================================
        async function openHistory() {
            historyModal.style.display = "flex";
            historyList.innerHTML = '<p style="text-align:center;color:#999;padding:20px;">加载中...</p>';

            try {
                const res = await fetch("/api/graph/list");
                const data = await res.json();
                if (!data.success || data.items.length === 0) {
                    historyList.innerHTML = '<p class="history-empty">暂无保存记录</p>';
                    return;
                }

                // 用 createElement 建 DOM（不用 innerHTML），addEventListener 直接绑定
                historyList.innerHTML = "";
                for (const item of data.items) {
                    const row = document.createElement("div");
                    row.className = "history-item";
                    row.addEventListener("click", () => loadGraph(item.id));

                    const info = document.createElement("div");
                    info.className = "history-item-info";

                    const topicEl = document.createElement("div");
                    topicEl.className = "hi-topic";
                    topicEl.textContent = item.topic;

                    const timeEl = document.createElement("div");
                    timeEl.className = "hi-time";
                    timeEl.textContent = item.created_at;

                    info.appendChild(topicEl);
                    info.appendChild(timeEl);

                    const delBtn = document.createElement("button");
                    delBtn.className = "hi-delete";
                    delBtn.textContent = "X";
                    delBtn.title = "删除";
                    delBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        if (!confirm("确定删除这个图谱？")) return;
                        deleteGraph(item.id);
                    });

                    row.appendChild(info);
                    row.appendChild(delBtn);
                    historyList.appendChild(row);
                }

            } catch (err) {
                console.error(err);
                historyList.innerHTML = '<p style="text-align:center;color:#ee6666;padding:20px;">加载失败</p>';
            }
        }

        function closeHistory() {
            historyModal.style.display = "none";
        }

        async function deleteGraph(graphId) {
            try {
                const res = await fetch(`/api/graph/delete/${graphId}`, { method: "DELETE" });
                if (!res.ok) {
                    const err = await res.json();
                    alert("删除失败：" + (err.detail || "未知错误"));
                    return;
                }
                // 删掉的正是当前画布上的图谱 → 画布、问答、输入框一起清空
                if (graphId === currentGraphId) {
                    currentGraphId = null;
                    currentGraph = { nodes: [], edges: [] };
                    currentTopic = "";
                    expansionMap = {};
                    expansionCache = {};
                    nodePositions = {};
                    activeNodeId = null;
                    topicInput.value = "";
                    chatMessages.innerHTML = "";
                    updateSaveBtn();
                    renderGraph();
                }
                openHistory(); // 刷新列表
            } catch (err) {
                console.error(err);
                alert("删除失败，请确认后端已启动");
            }
        }

        async function loadGraph(graphId) {
            closeHistory();
            currentGraph = { nodes: [], edges: [] };
            currentGraphId = null;   // 加载成功后才关联，失败不残留
            expansionMap = {};
            expansionCache = {};
            nodePositions = {};
            activeNodeId = null;
            chatMessages.innerHTML = "";
            chart?.showLoading({ text: "加载图谱中...", maskColor: "rgba(255,255,255,0.8)" });

            try {
                const res = await fetch(`/api/graph/load/${graphId}`);
                const data = await res.json();
                if (!data.success) { alert(data.message); return; }
                currentGraphId = graphId;   // 关联到这条记录，后续延伸自动同步
                currentGraph.nodes = data.graph.nodes;
                currentGraph.edges = data.graph.edges;
                currentTopic = "已加载 #" + graphId;
                topicInput.value = currentTopic;
                updateSaveBtn();
                renderGraph();
                loadChatHistory(graphId);   // 把这个图谱的问答记录也还原出来
            } catch (err) {
                console.error(err);
                alert("加载失败");
            } finally {
                chart?.hideLoading();
            }
        }

        // 还原某个图谱的历史问答
        async function loadChatHistory(graphId) {
            try {
                const res = await fetch(`/api/chat/history/${graphId}`);
                const data = await res.json();
                if (!data.success) return;
                for (const m of data.items) {
                    addMessage(m.role === "user" ? "user" : "ai", m.content);
                }
            } catch (e) {
                console.warn("问答历史加载失败（不影响使用）:", e);
            }
        }


        // ============================================================
        // 问答（SSE 流式）
        // ============================================================
        async function handleChat() {
            const question = chatInput.value.trim();
            if (!question) return;
            if (currentGraph.nodes.length === 0) return alert("请先生成一个知识图谱");

            addMessage("user", question);
            chatInput.value = "";

            const aiBubble = addMessage("ai", "");
            const aiContent = aiBubble.querySelector(".msg-content");

            // 流式回答期间禁用输入框和发送按钮，防止并发提问把气泡内容串在一起
            chatInput.disabled = true;
            sendBtn.disabled = true;

            try {
                const res = await fetch("/api/chat/ask", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question, graph: currentGraph, graph_id: currentGraphId }),
                });
                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = "", fullText = "";
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split("\n");
                    buffer = lines.pop() || "";
                    for (const line of lines) {
                        if (!line.startsWith("data: ")) continue;
                        const payload = line.slice(6).trim();
                        if (payload === "[DONE]") continue;
                        try {
                            const d = JSON.parse(payload);
                            if (d.token) {
                                fullText += d.token;
                                // 流式期间用户可能切换了图谱，气泡已被移除就别再更新
                                if (aiBubble.isConnected) {
                                    aiContent.textContent = fullText;
                                    chatMessages.scrollTop = chatMessages.scrollHeight;
                                }
                            }
                        } catch (e) { /* 忽略解析错误 */ }
                    }
                }
            } catch (err) {
                console.error(err);
                aiContent.textContent = "抱歉，网络出错了";
            } finally {
                // 回答结束（或出错）→ 恢复输入
                chatInput.disabled = false;
                sendBtn.disabled = false;
                chatInput.focus();
            }
        }

        function addMessage(role, text) {
            const div = document.createElement("div");
            div.className = `chat-message ${role}`;
            const avatarMap = { user: "🙋", ai: "🤖" };
            div.innerHTML = `<div class="msg-avatar">${avatarMap[role] || "?"}</div><div class="msg-bubble"><div class="msg-content">${escapeHtml(text)}</div></div>`;
            chatMessages.appendChild(div);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return div;
        }

        function escapeHtml(text) {
            const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
            return text.replace(/[&<>"']/g, c => map[c]);
        }


        // ============================================================
        // ECharts 渲染
        // ============================================================
        // 把画布上每个节点的当前坐标读出来，存进 nodePositions
        function capturePositions() {
            if (!chart) return;
            try {
                const seriesModel = chart.getModel().getSeriesByIndex(0);
                const graph = seriesModel && seriesModel.getGraph && seriesModel.getGraph();
                if (!graph) return;
                graph.eachNode(function (node) {
                    const layout = node.getLayout();
                    const id = node.getId();
                    if (layout && id) nodePositions[id] = { x: layout[0], y: layout[1] };
                });
            } catch (e) { /* 首次渲染还没有布局，忽略 */ }
        }

        function renderGraph() {
            if (!chart) return;
            const g = currentGraph;

            // ① 渲染前先记下旧节点坐标和缩放状态，渲染后原样恢复（防止乱跳）
            capturePositions();
            let prevZoom, prevCenter;
            try {
                const prev = chart.getOption();
                prevZoom = prev?.series?.[0]?.zoom;
                prevCenter = prev?.series?.[0]?.center;
            } catch (e) { /* 首次渲染没有旧 option */ }

            const catColors = {
                "概念": "#5470c6", "技术": "#91cc75",
                "人物": "#fac858", "理论": "#ee6666", "应用": "#73c0de",
            };
            const catSet = new Set();
            g.nodes.forEach(n => catSet.add(n.category));
            const categories = [...catSet].map(name => ({
                name,
                itemStyle: { color: catColors[name] || "#999" },
            }));

            const nodes = g.nodes.map(n => {
                const expanded = !!expansionMap[n.id];
                const active = n.id === activeNodeId;
                const pos = nodePositions[n.id];
                return {
                    id: n.id,
                    name: n.name + (expanded ? " ▼" : ""),
                    category: n.category,
                    // ② 旧节点带坐标 + fixed：力导向只排新节点，旧节点原地不动
                    ...(pos ? { x: pos.x, y: pos.y, fixed: true } : {}),
                    symbolSize: active ? 55 : 42,
                    label: {
                        show: true,
                        fontSize: active ? 13 : 12,
                        fontWeight: active ? "bold" : "normal",
                    },
                    itemStyle: expanded
                        ? { borderColor: "#52c41a", borderWidth: 3, shadowBlur: 8, shadowColor: "#52c41a" }
                        : active
                            ? { borderColor: "#ff6600", borderWidth: 3, shadowBlur: 10, shadowColor: "#ff6600" }
                            : { borderColor: "#fff", borderWidth: 1 },
                };
            });

            // 兜底：哪怕状态里混入了悬空边（比如旧版本存进数据库的），渲染前过滤掉
            const nodeIdSet = new Set(g.nodes.map(n => n.id));
            const links = g.edges
                .filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target))
                .map(e => ({
                    source: e.source,
                    target: e.target,
                    label: { show: true, formatter: e.label, fontSize: 10 },
                }));

            chart.setOption({
                title: {
                    text: g.nodes.length ? `知识图谱（${g.nodes.length} 节点, ${g.edges.length} 边）` : "",
                    left: "center",
                    top: 10,
                    textStyle: { fontSize: 15, color: "#333" },
                },
                tooltip: {
                    formatter: (p) => {
                        if (p.dataType === "edge") return `${p.data.source} → ${p.data.target}<br/>${p.data.label?.formatter || ""}`;
                        const exp = expansionMap[p.data.id];
                        const cached = expansionCache[p.data.id];
                        const hint = exp ? "点击收回" : cached ? "点击展开（恢复上次结果）" : "点击展开";
                        return `${p.data.name.replace(" ▼", "")}<br/>类别：${p.data.category || "?"}<br/><span style="color:#888">${hint}</span>`;
                    },
                },
                legend: { data: categories.map(c => c.name), bottom: 10 },
                series: [{
                    type: "graph",
                    layout: "force",
                    data: nodes,
                    links,
                    categories,
                    roam: true,
                    draggable: true,
                    // ③ 恢复上次的缩放/平移状态
                    ...(prevZoom ? { zoom: prevZoom } : {}),
                    ...(prevCenter ? { center: prevCenter } : {}),
                    force: {
                        repulsion: Math.min(500, 50 * g.nodes.length),
                        gravity: 0.08,
                        edgeLength: [80, 180],
                        layoutAnimation: true,
                    },
                    emphasis: {
                        focus: "adjacency",
                        lineStyle: { width: 3 },
                    },
                    lineStyle: { color: "#bbb", curveness: 0.2 },
                }],
            }, true);

            chart.off("click");
            chart.on("click", (params) => {
                if (params.dataType === "node") {
                    handleToggleNode(params.data.id, params.data.name.replace(" ▼", ""));
                }
            });
        }

        // ============================================================
        // 导出（PNG 图片 / JSON 文件）
        // ============================================================
        function safeFileName() {
            // 文件名里不能有特殊字符，做个简单清洗
            return (currentTopic || "graph").replace(/[\\/:*?"<>|\s]+/g, "_").slice(0, 50);
        }

        function handleExportPng() {
            if (!chart || currentGraph.nodes.length === 0) return;
            const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#ffffff" });
            const a = document.createElement("a");
            a.href = url;
            a.download = `hygraph-${safeFileName()}.png`;
            a.click();
        }

        function handleExportJson() {
            if (currentGraph.nodes.length === 0) return;
            const payload = {
                topic: currentTopic,
                graph_id: currentGraphId,
                exported_at: new Date().toISOString(),
                ...currentGraph,
            };
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = `hygraph-${safeFileName()}.json`;
            a.click();
            URL.revokeObjectURL(a.href);
        }

        function updateSaveBtn() {
            const empty = currentGraph.nodes.length === 0;
            saveBtn.disabled = empty;
            exportPngBtn.disabled = empty;
            exportJsonBtn.disabled = empty;
        }
    });
})();
