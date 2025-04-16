function addCommentNumbersWithLink() {
    const commentThreads = document.querySelectorAll('ytd-comment-thread-renderer');

    commentThreads.forEach((commentThread, index) => {
        // 이미 번호와 링크가 붙어있으면 중복 방지
        if (commentThread.querySelector('.comment-number')) return;

        // 번호를 붙일 엘리먼트 생성
        const numberTag = document.createElement('span');
        numberTag.className = 'comment-number';
        numberTag.textContent = ` #${index + 1} `; // 숫자 부분
        numberTag.style.color = 'red';

        // 네이버 링크 엘리먼트 생성
        const linkTag = document.createElement('a');
        linkTag.href = 'https://www.naver.com';
        linkTag.target = '_blank'; // 새 창으로 열기
        linkTag.textContent = '[NAVER]';

        // 링크 스타일 꾸미기 (선택 사항)
        linkTag.style.color = 'green';
        linkTag.style.fontWeight = 'bold';
        linkTag.style.marginLeft = '6px';
        linkTag.style.textDecoration = 'none';

        // 번호와 링크를 감싸줄 컨테이너도 만들어줌 (선택)
        const wrapper = document.createElement('span');
        wrapper.style.marginLeft = '8px'; // 아이디/시간과 간격 띄우기
        wrapper.appendChild(numberTag);
        wrapper.appendChild(linkTag);

        // 기존 작성자+시간 영역 뒤에 추가
        const header = commentThread.querySelector('#header-author');
        if (header) {
            header.appendChild(wrapper);
        }
    });
}

// 페이지 변화 감지해서 계속 실행
const observer = new MutationObserver(() => {
    addCommentNumbersWithLink();
});

// 처음 실행
addCommentNumbersWithLink();

// 변화 생길 때마다 실행
observer.observe(document.body, { childList: true, subtree: true });
