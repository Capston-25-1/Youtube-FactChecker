from flask import Flask, request, jsonify
from flask_cors import CORS
from factchecker import analyze_comment
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)


@app.route("/analyze", methods=["POST"])
def analyze_video():
    data = request.get_json()

    # 입력 데이터 추출
    video_url = data.get("video_url")
    video_title = data.get("video_title")
    comment = data.get("comment")

    fact_result = analyze_comment(comment)

    explaination = f"'{comment}'에 대한 팩트체크 결과입니다. 신뢰도가 {fact_result * 100:.1f}%입니다."
    related_articles = [
        {"title": "팩트체크 기사 1", "link": "https://example.com/article1"},
        {"title": "팩트체크 기사 2", "link": "https://example.com/article2"},
    ]

    response = {
        "fact_result": fact_result,
        "explaination": explaination,
        "related_articles": related_articles,
    }

    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True)
