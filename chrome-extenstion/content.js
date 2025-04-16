function addApiCallButton() {
    const commentThreads = document.querySelectorAll(
        "ytd-comment-thread-renderer"
    );

    commentThreads.forEach((commentThread, index) => {
        // 이미 버튼이 추가되어 있으면 중복 방지
        if (commentThread.querySelector(".api-call-button")) return;

        // API 호출 버튼 생성
        const apiButton = document.createElement("button");
        apiButton.textContent = "API 호출";
        apiButton.className = "api-call-button";
        apiButton.style.marginLeft = "8px";
        apiButton.style.padding = "4px 8px";
        apiButton.style.backgroundColor = "#f0f0f0";
        apiButton.style.border = "1px solid #ccc";
        apiButton.style.borderRadius = "4px";
        apiButton.style.cursor = "pointer";

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
            const factResult = await callYourAPI(commentText);

            if (factResult !== null) {
                // 결과 표시할 엘리먼트 생성
                const resultSpan = document.createElement("span");
                resultSpan.textContent = `Fact Result: ${factResult}`;
                resultSpan.style.marginLeft = "8px";
                resultSpan.style.color = "blue";
                resultSpan.style.fontWeight = "bold";
                header.appendChild(resultSpan);
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
        return data.fact_result; // "fact_result" 값 반환
    } catch (error) {
        console.error("API 호출 오류:", error);
        return null;
    }
}
