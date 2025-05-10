from flask import Flask, request, jsonify
from flask_cors import CORS
from factchecker import analyze_comment
from services.api import extract_keywords_batch_llm
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    comment = data["comment"]
    video_title = data.get("video_title", "")
    video_url   = data.get("video_url", "")
    fact_result, article_info = analyze_comment(comment)

    resp = {
        "fact_result": fact_result,
        "explaination": f"'{comment}'의 신뢰도는 {fact_result*100:.1f}%입니다.",
        "related_articles": [{"title": article_info[0], "link": article_info[1]}],
    }
    return jsonify(resp)

@app.route("/batch_extract", methods=["POST"])
def batch_extract():
    data       = request.get_json()
    comments   = data["comments"]
    video_ctx  = data.get("videoContext", {})       # 메타데이터 함께 받음
    results = extract_keywords_batch_llm(comments, video_ctx, n=6)
    return jsonify(results)
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
