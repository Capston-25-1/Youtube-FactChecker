const API_BASE = "http://localhost:5000";
const SEEN = new WeakSet();
const BUTTONED = new WeakSet();
const FLUSH_DELAY = 500;
const FONT_NAME = "Jua";
const CONFIDENCE_LEVEL = [
    {
        min: 0.0,
        max: 20.0,
        label: "🔴🚫 위험",
        description: "신뢰도가 매우 낮아 거짓일 가능성이 큰 문장입니다.",
    },
    {
        min: 20.0,
        max: 40.0,
        label: "🟡⚠️ 주의",
        description: "신뢰도가 낮은 편으로 판단에 주의를 요하는 문장입니다",
    },
    {
        min: 40.0,
        max: 60.0,
        label: "⚪❓ 중립",
        description: "중립적으로 사실 여부를 판단하기 어려운 문장입니다.",
    },
    {
        min: 60.0,
        max: 80.0,
        label: "🟢✅ 안전",
        description: "신뢰도가 높은 편으로 대체로 사실에 가까운 문장입니다.",
    },
    {
        min: 80.0,
        max: 100.0,
        label: "🔵⭕ 확신",
        description: "신뢰도가 매우 높아 사실일 가능성이 큰 문장입니다.",
    },
];
// -1일 때 "확인 불가" 표시(inference.py에서 검색된 모든 문장 유사도 값 낮은 경우)

let queueNodes = []; // 큐에 쌓인 댓글 노드
let timerId = null; // 디바운스 타이머

/** YouTube 영상 메타데이터 (제목·설명·해시태그만) */
function getVideoContext() {
    // 1) 제목: og:title 메타 태그
    const metaTitle = document.querySelector('meta[property="og:title"]');
    const title = (metaTitle?.content || "").trim();

    // 2) 설명: description 메타 태그
    const metaDesc = document.querySelector('meta[name="description"]');
    const description = (metaDesc?.content || "").trim();

    // 3) 해시태그: 설명창 안의 #링크들
    const tagEls = document.querySelectorAll(
        '#description a[href^="/hashtag/"]'
    );
    const hashtags = Array.from(tagEls)
        .map((a) => a.innerText.replace(/^#/, "").trim())
        .filter((t) => t);

    return { title, description, hashtags };
}

async function batchExtract(videoCtx, comments) {
    try {
        console.log("📝 [batch_extract payload]:", {
            videoContext: videoCtx,
            comments,
        });

        const resp = await fetch(`${API_BASE}/batch_extract`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ videoContext: videoCtx, comments }),
        });
        if (!resp.ok) throw new Error(`status ${resp.status}`);
        return await resp.json();
            } catch (e) {
        console.error("batch_extract 오류:", e);
        return {
            summary: "",
            claims: []
        };
    }
}

/** 팩트체크 API */
async function analyze(claim, keywords, summary) {
    console.log("📝 [analyze payload]:", { claim, keywords, summary });
    const resp = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({claim: claim, keyword: keywords, summary: summary  // 요약문만 전달
        })
    });
    if (!resp.ok) throw new Error(`status ${resp.status}`);

    const data = await resp.json();
    console.log("📝 [analyze result]:", data);

    return data;
}

/** 버튼 스타일 & 폰트 한번만 주입 */
(function injectAssets() {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${FONT_NAME.replace(
        / /g,
        "+"
    )}&display=swap`;
    document.head.appendChild(link);

    const style = document.createElement("style");
    style.textContent = `
    .api-call-button {
      padding:6px 12px;
      margin-left:8px;
      border:none;
      border-radius:999px;
      background:linear-gradient(135deg,#90a4ae,#546e7a);
      color:#dd2121;
      font-size:15px;
      font-family:"${FONT_NAME}",sans-serif;
      cursor:pointer;
      transition:background .3s,transform .2s;
      box-shadow:0 2px 5px rgba(0,0,0,.1)
    }
    .api-call-button:hover {
      background:linear-gradient(135deg,#78909c,#37474f);
      transform:scale(1.10)
    }

    .loading-spinner {
        display: none;
        position: relative;
        width: 15px;
        height: 15px;
        margin-left : 25px;
        border: 2px solid rgba(0, 0, 0, 0.1);
        border-top: 2px solid rgba(0, 0, 0, 0.6);
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    .loading-text {
        dispaly: none;
        postiion: relative;
        margin-left : 6px;
        color:#dd2121;
        font-size:15px;
        font-family:"${FONT_NAME}",sans-serif;
    }

    .tooltip-wrapper {
      position: relative;
      display: inline-block;
      cursor: pointer;
    }

    .tooltip-wrapper .tooltip {
      visibility: hidden;
      width: max-content;
      background-color: black;
      color: #fff;
      text-align: left;
      padding: 6px;
      border-radius: 4px;
      
      position: absolute;
      bottom: 125%;
      left: 50%;
      transform: translateX(-50%);
      z-index: 1;
       
      opacity: 0;
      transition: opacity 0.3s;
    }

    .tooltip-wrapper:hover .tooltip {
      visibility: visible;
      opacity: 1;
    }
    
    .tooltip-wrapper.core-tooltip .tooltip {
        max-width: 500px;
        white-space: normal;
        word-wrap: break-word;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
  `;
    document.head.appendChild(style);
})();

// 로딩 버튼 생성 및 표시
function createSpinner(selector) {
    const steps = [
        { message: "주장추출 중...", delay: 3000 },
        { message: "자료수집 중...", delay: 5000 },
        { message: "문장추출 중...", delay: 15000 },
        { message: "팩트체크 중...", delay: 5000 },
        { message: "신뢰도 계산 중...", delay: 5000 },
    ];

    // 로딩 바 생성
    let spinner = selector.querySelector(".loading-spinner");
    if (!spinner) {
        spinner = document.createElement("span");
        spinner.className = "loading-spinner";
        selector.appendChild(spinner);
    }
    spinner.style.display = "inline-block";

    // 텍스트 생성
    let text = selector.querySelector(".loading-text");
    if (!text) {
        text = document.createElement("span");
        text.className = "loading-text";
        // text.textContent = "분석 중...";
        let i = 0;
        function showNext() {
            if (i >= steps.length) return;
            text.textContent = steps[i].message;
            setTimeout(showNext, steps[i].delay);
            i++;
        }
        showNext();
        selector.appendChild(text);
    }
    text.style.display = "inline-block";
}

// 로딩 종료 시 숨김
function hideSpinner(selector) {
    const spinner = selector.querySelector(".loading-spinner");
    if (spinner) {
        spinner.style.display = "none";
    }

    const text = selector.querySelector(".loading-text");
    if (text) {
        text.style.display = "none";
    }
}

/** 댓글 노드에 버튼 달기 */
function attachButton(node, videoCtx, claims) {
    if (BUTTONED.has(node)) return;
    const header = node.querySelector("#header-author");
    if (!header) return;
    const btn = document.createElement("button");
    btn.className = "api-call-button";
    btn.textContent = "팩트체크";
    btn.addEventListener("click", async () => {
        btn.remove();
        createSpinner(header);
        // 버튼 클릭 시, 캐시된 추출 결과를 사용
        const cachedClaims = node.cachedClaims || [];
        const cachedSummary = node.cachedSummary || "";
        
        if (cachedClaims.length === 0) {
            console.error("캐시된 주장이 없습니다.");
            return;
        }
        // videoCtx 대신 summary 전달
        const analyses = await Promise.all(
            cachedClaims.map(c =>
                analyze(c.claim, c.keywords, { summary: cachedSummary })
                    .then(data => ({ claim: c.claim, ...data }))
                    .catch(() => ({ claim: c.claim, error: true }))
            )
        );
        renderResults(node, analyses);
        hideSpinner(header);
    });
    header.appendChild(btn);
    BUTTONED.add(node);
}

function categorize(x) {
    const result = CONFIDENCE_LEVEL.find(
        (r) => (x >= r.min && x < r.max) || (r.max === 100.0 && x === 100.0)
    );
    return result ? result : "평가 불가";
}

/** 결과 DOM 삽입 (복수 처리 버전) */
function renderResults(node, analyses) {
    let box = node.querySelector(".api-result-container");
    if (!box) {
        box = document.createElement("div");
        box.className = "api-result-container";
        box.style.marginLeft = "8px";
        node.querySelector("#header-author")?.appendChild(box);
    } else {
        box.innerHTML = "";
    }

    analyses.forEach((res) => {
        const wrap = document.createElement("div");
        wrap.style.marginBottom = "6px";

        // 1) 주장 텍스트
        const claimEl = document.createElement("div");
        claimEl.textContent = `주장: ${res.claim}`;
        claimEl.style.fontWeight = "bold";
        wrap.appendChild(claimEl);

        // 2) 신뢰도 구간 표시
        const confidence = parseFloat((res.fact_result * 100).toFixed(1));
        const fact = document.createElement("div");
        // fact.style.fontFamily = `${FONT_NAME}, sans-serif`;
        const category = categorize(confidence);
        fact.textContent = `분석 결과: ${category.label}(${confidence}%)`;
        fact.classList.add("tooltip-wrapper");
        const tooltip = document.createElement("div");
        tooltip.classList.add("tooltip");
        tooltip.textContent = `신뢰도 ${category.min}% ~ ${category.max}%: ${category.description}`;
        wrap.appendChild(fact);
        fact.appendChild(tooltip);

        // 3) 관련 기사 링크
        (res.related_articles || []).forEach((a) => {
            const link = document.createElement("a");
            link.href = a.link;
            link.target = "_blank";
            link.textContent = a.title;
            link.style.display = "block";
            link.style.marginLeft = "8px";

            if(a.core_sentence) {
                link.classList.add("tooltip-wrapper", "core-tooltip");
                const tooltipCore = document.createElement("div");
                tooltipCore.classList.add("tooltip");
                tooltipCore.textContent = a.core_sentence;
                link.appendChild(tooltipCore);
            }
            wrap.appendChild(link);
        });

        box.appendChild(wrap);
    });
}

/** DOM → 새 댓글 요소 배열(아직 keyword 추출 안 한 것만) */
function collectFreshComments() {
    return Array.from(
        document.querySelectorAll("ytd-comment-thread-renderer")
    ).filter((node) => !SEEN.has(node));
}

/** 메인 루프: 새 댓글 발견 → batch keyword 추출 → 버튼 주입 */
function processNewComments() {
    const fresh = collectFreshComments();
    if (!fresh.length) return;

    fresh.forEach((node) => {
        SEEN.add(node);
        queueNodes.push(node);
    });

    if (timerId) clearTimeout(timerId);
    timerId = setTimeout(flushQueue, FLUSH_DELAY);
}

async function flushQueue() {
    if (!queueNodes.length) return;
    const nodes = queueNodes.splice(0);
    const comments = nodes.map(
        (n) => n.querySelector("#content-text")?.innerText.trim() || ""
    );
    const videoCtx = getVideoContext();

    try {
        const response = await batchExtract(videoCtx, comments);
        console.log("[flushQueue] batchExtract results:", response);
        
        const { summary, claims } = response;
        console.log("[flushQueue] Video Summary:", summary);
        
        claims.forEach(({ index, claims }) => {
            if (claims && claims.some(c => c.keywords && c.keywords.length > 0)) {
                // 캐싱: 이미 추출된 claims를 댓글 노드에 저장
                nodes[index].cachedClaims = claims;
                nodes[index].cachedSummary = summary;
                attachButton(nodes[index], videoCtx);
            }
        });
    } catch (e) {
        console.error("flushQueue 오류:", e);
    }
}

/** 최초 실행 + MutationObserver */
processNewComments();
new MutationObserver(processNewComments).observe(document.body, {
    childList: true,
    subtree: true,
});
