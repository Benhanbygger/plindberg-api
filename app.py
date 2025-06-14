from flask import Flask, request, jsonify
import requests
import heapq
import traceback
import time
import os

app = Flask(__name__)

SERPSTAT_API_KEY = os.environ.get("SERPSTAT_API_KEY")
SERPSTAT_ENDPOINT = "https://api.serpstat.com/v4"

@app.route("/")
def home():
    return "✅ Flask API er live – klar til forespørgsler!"

def serpstat_request(method, params):
    headers = {"Content-Type": "application/json", "Token": SERPSTAT_API_KEY}
    payload = {"id": 1, "method": method, "params": params}

    try:
        resp = requests.post(SERPSTAT_ENDPOINT, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        time.sleep(1.1)
        return resp.json()
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout ved Serpstat-kald: {method}")
        raise Exception(f"Timeout fra Serpstat på metode: {method}")
    except Exception as e:
        print(f"🚨 Serpstat-fejl ({method}): {e}")
        raise Exception(f"Serpstat API-fejl ({method}): {e}")

def get_keyword_info(keyword):
    data = serpstat_request("SerpstatKeywordProcedure.getKeywordsInfo", {
        "keywords": [keyword],
        "se": "g_dk"
    })
    try:
        info = data["result"]["data"][0]
    except (KeyError, IndexError):
        raise ValueError(f"❌ Ingen data fundet for keyword: {keyword}")
    return {
        "keyword": keyword,
        "volume": info["region_queries_count"],
        "difficulty": info["difficulty"]
    }

def get_domain_position(keyword, domain):
    def normalize_domain(d):
        return d.lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")

    data = serpstat_request("SerpstatKeywordProcedure.getKeywordFullTop", {
        "keyword": keyword,
        "se": "g_dk"
    })
    top_data = data.get("result", {}).get("hits", [])
    for item in top_data:
        item_domain = normalize_domain(item.get("domain", ""))
        target_domain = normalize_domain(domain)
        if target_domain in item_domain:
            return item["position"]
    return "N/A"

def get_related_keywords(keyword):
    data = serpstat_request("SerpstatKeywordProcedure.getRelatedKeywords", {
        "keyword": keyword,
        "se": "g_dk"
    })
    related_raw = data.get("result", {}).get("data", [])
    keywords = [k["keyword"] for k in related_raw]
    return keywords

@app.route("/keyword-analysis", methods=["GET"])
def keyword_analysis():
    keywords = request.args.getlist("keyword")
    domain = request.args.get("domain", "p-lindberg.dk")
    if not keywords:
        return jsonify({"error": "Missing 'keyword' parameter"}), 400

    results = []

    for keyword in keywords:
        try:
            primary_info = get_keyword_info(keyword)
            primary_position = get_domain_position(keyword, domain)
            primary_info["position"] = primary_position

            related_keywords = get_related_keywords(keyword)[:20]
            scored_related = []
            lavthaengende_frugter = []

            for rk in related_keywords:
                try:
                    info = get_keyword_info(rk)
                    position = get_domain_position(rk, domain)

                    if info["volume"] is not None and info["difficulty"] is not None:
                        info["score"] = info["volume"] - info["difficulty"]
                    else:
                        info["score"] = 0

                    info["position"] = position
                    scored_related.append(info)

                    if isinstance(position, int) and 4 <= position <= 21:
                        lavthaengende_frugter.append(info)

                except Exception as inner_e:
                    print(f"ERROR processing related keyword '{rk}': {inner_e}")
                    traceback.print_exc()

            top_related = heapq.nlargest(5, scored_related, key=lambda x: x["score"])

            results.append({
                "keyword": keyword,
                "primary": primary_info,
                "related_keywords": top_related,
                "lavthaengende_frugter": lavthaengende_frugter
            })

        except Exception as e:
            print(f"Fejl ved keyword '{keyword}': {e}")
            traceback.print_exc()
            results.append({
                "keyword": keyword,
                "error": str(e)
            })

    return jsonify(results)

@app.route("/find-ranking-keywords", methods=["GET"])
def find_ranking_keywords():
    seed_keywords = request.args.getlist("keyword")
    domain = request.args.get("domain", "p-lindberg.dk")
    results = []

    for kw in seed_keywords:
        position = get_domain_position(kw, domain)
        if position != "N/A":
            results.append({
                "keyword": kw,
                "position": position
            })

    return jsonify(results)

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({
        "error": str(e),
        "trace": traceback.format_exc()
    }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
