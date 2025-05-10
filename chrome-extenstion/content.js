const API_BASE    = "http://localhost:5000";
const SEEN        = new WeakSet();
const BUTTONED    = new WeakSet();
const FLUSH_DELAY = 3000;
const fontName = "Jua";

let queueNodes = [];     // 큐에 쌓인 댓글 노드
let timerId    = null;   // 디바운스 타이머

/** YouTube 영상 메타데이터 (제목·설명·해시태그만) */
function getVideoContext() {
  const titleEl = document.querySelector('h1.title yt-formatted-string');
  const descEl  = document.querySelector('#description');
  const tagEls  = document.querySelectorAll(
    '#above-the-fold #description a[href*="/hashtag/"]'
  );
  return {
    title:       titleEl?.innerText?.trim() || "",
    description: descEl?.innerText?.trim() || "",
    hashtags:    Array.from(tagEls).map(a => a.innerText.replace('#','').trim())
  };
}


/** DOM → 새 댓글 요소 배열(아직 keyword 추출 안 한 것만) */
function collectFreshComments() {
  return Array.from(document.querySelectorAll("ytd-comment-thread-renderer"))
              .filter(node => !SEEN.has(node));
}

async function batchExtract(videoCtx, comments) {
  try {
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
function attachButton(node, videoCtx, keywords){
  if (BUTTONED.has(node)) return;
  const header = node.querySelector("#header-author");
  if (!header) return;

  const btn = document.createElement("button");
  btn.className="api-call-button";
  btn.textContent="팩트체크";
  btn.addEventListener("click", async ()=>{
    btn.remove();  // 중복 호출 방지
    const commentText = node.querySelector("#content-text")?.innerText || "";
    try{
      const data = await analyze(commentText, videoCtx);
      renderResult(node, data);
    }catch(e){ console.error("analyze 오류:", e); }
  });
  header.appendChild(btn);
  BUTTONED.add(node);
}

/** 결과 DOM 삽입 */
function renderResult(node, data){
  let box = node.querySelector(".api-result-container");
  if (!box){
    box = document.createElement("div");
    box.className="api-result-container"; box.style.marginLeft="8px";
    node.querySelector("#header-author")?.appendChild(box);
  } else box.innerHTML="";

  const fact = document.createElement("span");
  fact.style.color="blue"; fact.style.fontWeight="bold";
  fact.textContent=`Fact Result: ${(data.fact_result*100).toFixed(1)}%`;
  box.appendChild(fact);

  (data.related_articles||[]).forEach(a=>{
    const link = document.createElement("a");
    link.target="_blank"; link.href=a.link;
    link.style="margin-left:8px;color:green;font-weight:bold";
    link.textContent=a.title;
    box.appendChild(link);
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
  console.log("flushQueue 호출, 노드 개수:", queueNodes.length);

  const nodes    = queueNodes.splice(0);
  const comments = nodes.map(n =>
    n.querySelector("#content-text")?.innerText?.trim() || ""
  );
  const videoCtx = getVideoContext();

  try {
    const results = await batchExtract(videoCtx, comments);
    results.forEach(({index, keywords}) => {
      if (keywords && keywords.length) {
        attachButton(nodes[index], videoCtx, keywords);
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
