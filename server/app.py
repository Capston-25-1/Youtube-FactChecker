import os
import pandas as pd
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

from services.api import extract_keywords_batch_llm
from factcheck_engine import CommentFactCheck
from dotenv import load_dotenv

from threading import Thread

load_dotenv()

app = Flask(__name__)
CORS(app)


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    claim = data["claim"]
    video_ctx = {
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "hashtags": data.get("hashtags", []),
    }
    video_summary = data.get("summary", "")
    keywords = data["keyword"]
    print(keywords)
    factchecker = CommentFactCheck(claim, keywords, video_ctx, video_summary["summary"])

    factchecker.analyze()
    # fact_result, article_info = analyze_comment(comment)
    explaination = f"'{claim}'에 대한 팩트체크 결과입니다. 신뢰도가 {factchecker.score * 100:.1f}%입니다."
    related_articles = [
        {
            "title": factchecker.best_article[0],
            "link": factchecker.best_article[1],
            "core_sentence": factchecker.best_sentence,
        },
    ]

    response = {
        "fact_result": factchecker.score,
        "explaination": explaination,
        "related_articles": related_articles,
    }
    Thread(target=factchecker.cache_result).start()
    return jsonify(response)


@app.route("/batch_extract", methods=["POST"])
def batch_extract():
    data = request.get_json()
    comments = data["comments"]
    video_ctx = data.get("videoContext", {})  # 메타데이터 함께 받음
    results = extract_keywords_batch_llm(comments, video_ctx, n=6)
    return jsonify(results)


# get fact-check result for all comemnts
@app.route("/factcheck", methods=["POST"])
def analyze_comments():
    data = request.get_json()

    # 입력 데이터 추출
    video_url = data.get("video_url")
    video_title = data.get("video_title")
    video_tag = data.get("video_tag")

    # get keyword form video information
    comments = data.get("comments")
    response = {"data": []}
    for index, comment in enumerate(comments):
        fact_result, article_info = analyze_comment(comment)

        explaination = f"'{comment}'에 대한 팩트체크 결과입니다. 신뢰도가 {fact_result * 100:.1f}%입니다."
        related_articles = [
            {"title": article_info[0], "link": article_info[1]},
        ]

        result = {
            "comment_index": index,
            "fact_result": fact_result,
            "explaination": explaination,
            "related_articles": related_articles,
        }
        response["data"].append(result)
    return jsonify(response)


@app.route(
    "/test_keywords", methods=["POST"]
)  # curl.exe -X POST http://localhost:5000/test_keywords 실행
def test_keywords():
    video_ctx = {
        "title": "'백종원 내로남불 전형'…대중이 등 돌린 진짜 이유 [잇슈 머니] / KBS  2025.05.09.",
        "description": "박연미 경제평론가 나오셨습니다.오늘 키워드는,  '백종원 사태, 상장이 문제였다'라고 하셨는데, 최근 잇따른 논란으로 사과한 백종원 더본코리아 대표 얘긴가요? [답변]네, 맞습니다. 유명 외식 프랜차이즈 대표이자 방송인 백종원 더본코리아 대표가 세 번째로 고개를 숙였지만, 주가와 ...",
        "hashtags": ["백종원", "더본코리아", "내로남불"],
    }

    comments = [
        "골목식당 최종 빌런은 저 사람 이였다. ㅋㅋㅋㅋㅋ",
        "사기꾼  백종원을  방송이  영웅 만들어줬지,  방송도  책임져야한다.",
        "문제는  백종원을 키워준 방송국이 책임져야 한다",
        "상장이고 나발이고 그냥 사람새기 아니었다가 맞다.   공항인터뷰 기가 차더라 진짜.",
        "종원이 유명하게 만들어 놓고 꿀빨던 PD들. .응 니들.. 모르는척 하지말고 빨리 나와서 국민들에게 사과해.",
        "본인이방송활동중단한게아니라사실상퇴출이지.",
        "그 동안 백종원의 몸 값을 올린 것은 언론.  언론의 책임이 가장 큰데 불구하고 사과하는 언론 한 곳 없네.   이 나라에 언론다운 언론이 없다는게 가장 큰 문제.",
        "우삼겹, 대패 삼겹살, 시레기만두 다 본인이 개발했다는 주장에 어이가 없었지",
        "농약통 뭐 어때서유\n새거라니까? \n (구리스 및 스틸가루함유)",
        "최악의 인물~~ 가맹점이 힘들다고 얘기했는데 개무시하다가 언론에서 계속 각종 문제점 들추니까 이미지 개선할 목적으로 가맹점 지원한다고 개소리함. 전형적인 독불장군식 CEO의 표본이고 결국 대중에 의해 망하게 될 것임.",
        '사과의 방식이 잘못됐다. "모든문제에 수사를 성실히 받고 죄가있다면 처벌받고 즉각 시정하겠다"가 맞다. 방송접는건 당연한거고 본인 기업 본인이 더 신경쓴다는게 사과냐?',
        "백종원  구속시켜야된다 먹는음식같고  국민들 한테 사기그만쳐라  구속하고 세무조사 해야한다",
        "전문 요리사도 아닌데 띄워준 방송국놈들이 제일 문제 아닌가?",
        "대단한 맨탈이야\n이 상황에 다시 방송출연 의욕있음",
        '손석희 방송에 나와서 한 말이 진짜 충격이였지 "다른 점주들은 신났어유" ㅋ',
        "그동안 방송국 뒤에 업은 백가는 선생님 선생님 해주니까 본인이 뭐라도 되는양 요리장인들에게 호통을 치고 연예인들을 아랫사람 부리듯 하며 살아왔는데... 본인이  주제넘었다 생각하고 자중하고 작작 했어야했다.  오히려 스스로 뭐라도 되는듯 맘껏 누리며 살아와서 지금 대가를 치르는듯. 자업자득이다",
        "군산은 왜...더본에 저 정도까지 해다 바친 걸까 ㄷㄷ",
        "방송 이미지로 회사 상장시켰으니 방송 못 나오게 막아야 됨. 그래야 일어나지 못 함",
        "즉각 모든 방송에서 하차해야지. 이미 찍어 놓은건 방송을 하겠단거잖아. 그리고 논란중인데 방송을 찍고 왔고 유출영상보니 방송으로 이미지 다시 개선할려는 꼼수가 보이는데 사과가 진정으로 와 닿겠냐??정말 내로남불의 전형이다. ㅠㅠ",
        '"농약통 새거라니깐?"(실제로 한 말)',
        "실력은 뽀록에 본색은 저질, 내로남불, 돈만 밝힘, 자존감 낮음",
        "사기 천재 백가",
        "허위 사실로 소비자 기만 \n이 사실 하나만으로도 형사처벌이다!! \n사과도 필요없고 그냥 방송 그만나와라!!",
        "연돈이 연매출 13억인데 순수익이 7000... 그것도 부부 둘이 하시니까 빡세게 돈가스 장사하면서 3500가져가는건데 백종원한테 제대로 걸린듯.. 그냥 유배 간 느낌이실듯..",
        "''농약통이 뭐 어때유~ 새거인데유'' 라고 하는 건 마치 ''변기통이 뭐 어때유 ~ 도자기인데유~''라고 하는 것과 유사함.",
        "말은 바로 해야지 방송중단이 아니라, 퇴출이나 마찬가지지.  못하게 될것 같으니 중단하겠다고",
        "백종팔 구속 시켜라 어차피 저인간 뭐가 문제인지도 모른다 사과도 마지못해 하는척 하는거지",
        "백종원씨 사과는 머리를 아레로\n쳐박고 하는겁니다 브리핑\n서류 들고. 반박하는게 아니죠",
        "언론과 방송이 괴물을 만들었다!",
        "그것보다 골목식당하면서 폐업한분들 보상먼저 하는게",
        "백악마~~구속하고 세무조사 시켜야 함",
        "소유진하고 왜 결혼하지 그랬는데 ㅋㅋ 끼리끼리였다 ㅋㅋㅋ",
        "지겹네!! 빽!그만좀 티비에 나왓음!!보고 배울게 없는 인간을 왜캐 띠워주는지?? 사기치고 양심이란것은 밥말아먹는거 배우란뜻",
        "백씨가 요리사 자격증 없는 것을 자랑스럽게 이야기 하는 모습이 가장 어의가 없었다 요리의 기본도 모르는 데, 요리의 대가... 방송국 놈들도 다 한패야!",
        "사람 먹는 음식에 장난질을 하대면 벌받아야됩니다",
    ]

    # 키워드 추출 실행
    try:
        results = extract_keywords_batch_llm(comments, video_ctx)
        if not results:
            results = [None] * len(comments)
    except Exception as e:
        print(f"키워드 추출 중 오류 발생: {str(e)}")
        results = [None] * len(comments)
    excel_data = []
    for i, comment in enumerate(comments):
        row = {"댓글": comment, "주장": "", "키워드": ""}

        # results에서 해당 인덱스의 결과 찾기
        result = next((r for r in results if r["index"] == i), None)
        if result and result.get("claims"):
            claims_list = []
            keywords_list = []

            for claim_data in result["claims"]:
                if claim := claim_data.get("claim"):
                    claims_list.append(claim)
                    keywords = claim_data.get("keywords", [])
                    if keywords:
                        keywords_list.append("{" + ",".join(keywords) + "}")

            row["주장"] = ", ".join(claims_list)
            row["키워드"] = " ".join(keywords_list)

        excel_data.append(row)

    # DataFrame 생성 및 엑셀로 저장
    df = pd.DataFrame(excel_data)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = os.path.join("results", "keyword_results.xlsx")
    os.makedirs("results", exist_ok=True)

    try:
        with pd.ExcelWriter(
            excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace"
        ) as writer:
            df.to_excel(writer, sheet_name=f"Sheet_{timestamp}", index=False)
    except FileNotFoundError:
        df.to_excel(excel_path, index=False, sheet_name="Sheet1")

    return jsonify({"results": results, "excel_file": excel_path})


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
