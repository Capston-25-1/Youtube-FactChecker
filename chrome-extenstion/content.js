function addApiCallButton() {
    const commentThreads = document.querySelectorAll(
        "ytd-comment-thread-renderer"
    );

    commentThreads.forEach((commentThread, index) => {
        // 이미 버튼이 추가되어 있으면 중복 방지
        if (commentThread.querySelector(".api-call-button")) return;

        // Google Fonts 적용
        const fontLink = document.createElement("link");
        const fontName = "Jua";
        const fontQuery = fontName.replace(/ /g, "+");
        fontLink.href = `https://fonts.googleapis.com/css2?family=${fontQuery}&display=swap`; //Do+Hyeon
        fontLink.rel = "stylesheet";
        document.head.appendChild(fontLink);

        // API 호출 버튼 생성
        const apiButton = document.createElement("button");
        apiButton.textContent = "팩트체크!";
        apiButton.className = "api-call-button";

        // apiButton.style.marginLeft = "8px";
        // apiButton.style.padding = "4px 8px";
        // apiButton.style.backgroundColor = "#f0f0f0";
        // apiButton.style.border = "1px solid #ccc";
        // apiButton.style.borderRadius = "999px";
        // apiButton.style.cursor = "pointer";
        // apiButton.style.fontFamily =`"${fontName}", sans-serif`  // "'Do Hyeon', sans-serif"
        // apiButton.style.fontSize = "15px";

        // CSS 설정

        // 분홍+하늘 linear-gradient(135deg, #f8bbd0, #bbdefb); h:linear-gradient(135deg, #f48fb1, #90caf9)
        // 파랑 linear-gradient(135deg, #4dd0e1, #1976d2); h:linear-gradient(135deg, #f48fb1, #90caf9)
        // 라임 → 중녹색 linear-gradient(135deg, #aed581, #7cb342); h:linear-gradient(135deg, #9ccc65, #558b2f);
        // 검회색 linear-gradient(135deg, #90a4ae, #546e7a); h:linear-gradient(135deg, #78909c, #37474f);

        const style = document.createElement("style");
        style.textContent = `
        .api-call-button {
          padding: 6px 12px;
          margin-left: 8px;
          border: none;
          border-radius: 999px;
          background: linear-gradient(135deg, #90a4ae, #546e7a);
          color: #dd2121;
          font-size: 15px;
          font-family: "${fontName}", sans-serif;
          cursor: pointer;
          transition: background 0.3s ease, transform 0.2s ease;
          box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .api-call-button:hover {
          background: linear-gradient(135deg, #78909c, #37474f);
          transform: scale(1.10);
        }
      `;
        document.head.appendChild(style);        

        // 기존 작성자+시간 영역 뒤에 추가
        const header = commentThread.querySelector("#header-author");
        if (header) {
            header.appendChild(apiButton);
        }

        // 버튼 클릭 이벤트 리스너 추가
        apiButton.addEventListener("click", async () => {
            const commentTextElement =
                commentThread.querySelector("#content-text");
            const commentText = commentTextElement
                ? commentTextElement.textContent
                : "";

            // 버튼 사라지게 하기
            apiButton.remove();

            // API 호출 및 결과 처리
            const apiResponse = await callYourAPI(commentText);

            if (apiResponse !== null) {
                const factResult = apiResponse.fact_result;
                const relatedArticles = apiResponse.related_articles;

                // 결과 표시 영역 생성 또는 찾기
                let resultContainer = commentThread.querySelector(".api-result-container");
                if (!resultContainer) {
                    resultContainer = document.createElement("div");
                    resultContainer.className = "api-result-container";
                    resultContainer.style.marginLeft = "8px";
                    header.appendChild(resultContainer);
                } else {
                    // 이미 결과가 있으면 초기화
                    resultContainer.innerHTML = "";
                }

                // Fact Result 표시
                const factSpan = document.createElement("span");
                factSpan.textContent = `Fact Result: ${(factResult * 100).toFixed(1)}%`;
                factSpan.style.color = "blue";
                factSpan.style.fontWeight = "bold";
                resultContainer.appendChild(factSpan);

                // 관련 기사 표시
                if (relatedArticles && relatedArticles.length > 0) {
                    relatedArticles.forEach(article => {
                        const articleLink = document.createElement("a");
                        articleLink.textContent = article.title;
                        articleLink.href = article.link;
                        articleLink.target = "_blank"; // 새 탭에서 열기
                        articleLink.style.marginLeft = "8px";
                        articleLink.style.color = "green";
                        articleLink.style.fontWeight = "bold";
                        resultContainer.appendChild(articleLink);
                    });
                }
            }
        });
    });
}

// 페이지 변화 감지해서 계속 실행
const observer = new MutationObserver(() => {
    addApiCallButton();
});

// 처음 실행
addApiCallButton();

// 변화 생길 때마다 실행
observer.observe(document.body, { childList: true, subtree: true });

// API 호출 함수 (async/await 사용)
async function callYourAPI(commentText) {
    const apiUrl = "http://localhost:5000/analyze"; // 실제 API 엔드포인트로 변경

    try {
        const response = await fetch(apiUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ comment: commentText }),
        });

        if (!response.ok) {
            console.error(`API error! status: ${response.status}`);
            return null;
        }

        const data = await response.json();
        return data; // 전체 API 응답 객체 반환
    } catch (error) {
        console.error("API 호출 오류:", error);
        return null;
    }
}