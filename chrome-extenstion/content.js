const API_BASE    = "http://localhost:5000";
const SEEN        = new WeakSet();
const BUTTONED    = new WeakSet();
const FLUSH_DELAY = 3000;
const fontName = "Jua";

let queueNodes = [];     // 큐에 쌓인 댓글 노드
let timerId    = null;   // 디바운스 타이머

/** YouTube 영상 메타데이터 (제목·설명·해시태그만) */
function getVideoContext() {
  // 1) 제목: og:title 메타 태그
  const metaTitle = document.querySelector('meta[property="og:title"]');
  const title = (metaTitle?.content || "").trim();

  // 2) 설명: description 메타 태그
  const metaDesc  = document.querySelector('meta[name="description"]');
  const description = (metaDesc?.content || "").trim();

  // 3) 해시태그: 설명창 안의 #링크들
  const tagEls = document.querySelectorAll(
    '#description a[href^="/hashtag/"]'
  );
  const hashtags = Array.from(tagEls)
    .map(a => a.innerText.replace(/^#/, "").trim())
    .filter(t => t);

  return { title, description, hashtags };
}


/** DOM → 새 댓글 요소 배열(아직 keyword 추출 안 한 것만) */
function collectFreshComments() {
  return Array.from(document.querySelectorAll("ytd-comment-thread-renderer"))
              .filter(node => !SEEN.has(node));
}

async function batchExtract(videoCtx, comments) {
  try {
    console.log("📝 [batch_extract payload]:", { videoContext: videoCtx, comments });

    const resp = await fetch(`${API_BASE}/batch_extract`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ videoContext: videoCtx, comments })
    });
    if (!resp.ok) throw new Error(`status ${resp.status}`);
    return await resp.json();
  } catch(e) {
    console.error("batch_extract 오류:", e);
    return [];
  }
}

/** 팩트체크 API */
async function analyze(comment, videoCtx) {
  console.log("📝 [analyze payload]:", { comment, ...videoCtx });

  const resp = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ comment, ...videoCtx })
  });
  if (!resp.ok) throw new Error(`status ${resp.status}`);
  return resp.json();
}

/** 버튼 스타일 & 폰트 한번만 주입 */
(function injectAssets(){
  const link = document.createElement("link");
  link.rel="stylesheet";
  link.href=`https://fonts.googleapis.com/css2?family=${fontName.replace(/ /g,"+")}&display=swap`;
  document.head.appendChild(link);

  const style = document.createElement("style");
  style.textContent = `
    .api-call-button{
      padding:6px 12px;margin-left:8px;border:none;border-radius:999px;
      background:linear-gradient(135deg,#90a4ae,#546e7a);
      color:#dd2121;font-size:15px;font-family:"${fontName}",sans-serif;
      cursor:pointer;transition:background .3s,transform .2s;
      box-shadow:0 2px 5px rgba(0,0,0,.1)
    }
    .api-call-button:hover{
      background:linear-gradient(135deg,#78909c,#37474f);transform:scale(1.10)
    }
  `;
  document.head.appendChild(style);
})();

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

    // 1) 해당 댓글만 다시 batchExtract 호출
    const commentText = node.querySelector("#content-text")?.innerText || "";
    let batchRes = [];
    try {
      batchRes = await batchExtract(videoCtx, [commentText]);
    } catch (e) {
      console.error("재추출 오류:", e);
    }
    console.log("[attachButton] single-extract claims:", batchRes[0]?.claims);

    // batchRes[0].claims == [{claim, keywords}, ...]
    const newClaims = (batchRes[0] && batchRes[0].claims) || [];

    // 2) 모든 뽑힌 주장에 대해 팩트체크
    const analyses = await Promise.all(
    newClaims.map(c =>
      analyze(c.claim, c.keywords, videoCtx)
        .then(data => ({ claim: c.claim, ...data }))
        .catch(() => ({ claim: c.claim, error: true }))
    )
    );

    // 3) 기존과 동일하게 렌더링
    renderResults(node, analyses);
  });

  header.appendChild(btn);
  BUTTONED.add(node);
}


/** 결과 DOM 삽입 (복수 처리 버전) */
function renderResults(node, analyses){
  let box = node.querySelector(".api-result-container");
  if (!box){
    box = document.createElement("div");
    box.className = "api-result-container";
    box.style.marginLeft = "8px";
    node.querySelector("#header-author")?.appendChild(box);
  } else {
    box.innerHTML = "";
  }

  analyses.forEach(res => {
    const wrap = document.createElement("div");
    wrap.style.marginBottom = "6px";

    // 1) 주장 텍스트
    const claimEl = document.createElement("div");
    claimEl.textContent = `주장: ${res.claim}`;
    claimEl.style.fontWeight = "bold";
    wrap.appendChild(claimEl);

    // 2) 신뢰도 표시
    const fact = document.createElement("div");
    fact.textContent = `신뢰도: ${(res.fact_result*100).toFixed(1)}%`;
    wrap.appendChild(fact);

    // 3) 관련 기사 링크
    (res.related_articles||[]).forEach(a => {
      const link = document.createElement("a");
      link.href = a.link;
      link.target = "_blank";
      link.textContent = a.title;
      link.style.display = "block";
      link.style.marginLeft = "8px";
      wrap.appendChild(link);
    });

    box.appendChild(wrap);
  });
}


/** 메인 루프: 새 댓글 발견 → batch keyword 추출 → 버튼 주입 */
function processNewComments() {
  const fresh = Array.from(
    document.querySelectorAll("ytd-comment-thread-renderer")
  ).filter(n => !SEEN.has(n));
  if (!fresh.length) return;

  fresh.forEach(node => {
    SEEN.add(node);
    queueNodes.push(node);
  });

  if (timerId) clearTimeout(timerId);
  timerId = setTimeout(flushQueue, FLUSH_DELAY);
}

async function flushQueue() {
  if (!queueNodes.length) return;
  const nodes    = queueNodes.splice(0);
  const comments = nodes.map(n => 
    n.querySelector("#content-text")?.innerText.trim() || ""
  );
  const videoCtx = getVideoContext();

  try {
    const results = await batchExtract(videoCtx, comments);
    console.log("[flushQueue] batchExtract results:", results);
    results.forEach(({index, claims}) => {
      // claims 배열이 비어있으면 버튼 달지 않음
      if (claims && claims.length) {
        attachButton(nodes[index], videoCtx, claims);
      }
    });
  } catch(e) {
    console.error("flushQueue 오류:", e);
  }
}

/** 최초 실행 + MutationObserver */
processNewComments();
new MutationObserver(processNewComments)
  .observe(document.body, {childList:true, subtree:true});
