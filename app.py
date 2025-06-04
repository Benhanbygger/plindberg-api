from flask import Flask, request, jsonify
import requests
import heapq
import traceback
import time

app = Flask(__name__)
import os
SERPSTAT_API_KEY = os.environ.get("SERPSTAT_API_KEY")
SERPSTAT_ENDPOINT = "https://api.serpstat.com/v4"

def serpstat_request(method, params):
    headers = {"Content-Type": "application/json", "Token": SERPSTAT_API_KEY}
    payload = {"id": 1, "method": method, "params": params}
    resp = requests.post(SERPSTAT_ENDPOINT, json=payload, headers=headers)
    resp.raise_for_status()
    time.sleep(1.1)  # Pause efter hvert kald
    return resp.json()

def get_keyword_info(keyword):
    data = serpstat_request("SerpstatKeywordProcedure.getKeywordsInfo", {
        "keywords": [keyword],
        "se": "g_dk"
    })
    print(f"\nDEBUG keyword_info for '{keyword}':\n{data}")
    info = data["result"]["data"][0]
    return {
        "keyword": keyword,
        "volume": info["region_queries_count"],
        "difficulty": info["difficulty"]
    }

def get_domain_position(keyword, domain):
    data = serpstat_request("SerpstatKeywordProcedure.getKeywordFullTop", {
        "keyword": keyword,
        "se": "g_dk"
    })
    print(f"\nDEBUG domain_position for '{keyword}':\n{data}")
    top_data = data.get("result", {}).get("hits", [])
    for item in top_data:
        if domain in item.get("domain", ""):
            return item["position"]
    return "N/A"

def get_related_keywords(keyword):
    data = serpstat_request("SerpstatKeywordProcedure.getRelatedKeywords", {
        "keyword": keyword,
        "se": "g_dk"
    })
    print(f"\nDEBUG related_keywords for '{keyword}':\n{data}")
    related_raw = data.get("result", {}).get("data", [])
    keywords = [k["keyword"] for k in related_raw]
    return keywords

@app.route("/keyword-analysis", methods=["GET"])
def keyword_analysis():
    keywords = request.args.getlist("keyword")
    domain = request.args.get("domain", "p-lindberg.dk")
    if not keywords:
        return jsonify({"error": "Missing 'keyword' parameter"}), 400

    try:
        results = []

        for keyword in keywords:
            primary_info = get_keyword_info(keyword)
            primary_position = get_domain_position(keyword, domain)
            primary_info["position"] = primary_position

            related_keywords = get_related_keywords(keyword)[:20]
            scored_related = []
            for rk in related_keywords:
                try:
                    info = get_keyword_info(rk)
                    score = info["volume"] - info["difficulty"]
                    info["score"] = score
                    info["position"] = get_domain_position(rk, domain)
                    scored_related.append(info)
                except Exception as inner_e:
                    print(f"\nERROR processing related keyword '{rk}': {inner_e}")
                    traceback.print_exc()
                    continue
            top_related = heapq.nlargest(5, scored_related, key=lambda x: x["score"])

            results.append({
                "keyword": keyword,
                "primary": primary_info,
                "related_keywords": top_related
            })

        return jsonify(results)

    except Exception as e:
        print("\nGENERAL ERROR:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
