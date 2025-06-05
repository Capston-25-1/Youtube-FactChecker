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
    keywords = data["keyword"]
    print(keywords)
    factchecker = CommentFactCheck(claim, keywords, video_ctx)

    factchecker.analyze()
    # fact_result, article_info = analyze_comment(comment)
    explaination = f"'{claim}'에 대한 팩트체크 결과입니다. 신뢰도가 {factchecker.score * 100:.1f}%입니다."
    related_articles = [
        {"title": factchecker.best_article[0], "link": factchecker.best_article[1]},
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)