from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import re
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

def get_price(code):
    try:
        url = f"https://m.stock.naver.com/api/stock/{code}/basic"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=(3, 5))
        res.raise_for_status()
        data = res.json()
        if not isinstance(data, dict) or data.get("itemCode") != code:
            raise ValueError("Quote code does not match requested code")
        raw = str(data.get("closePrice", "")).replace(",", "")
        if not re.fullmatch(r"[0-9]+", raw) or int(raw) <= 0:
            raise ValueError("Quote price is missing or invalid")
        return int(raw)
    except (requests.RequestException, ValueError) as error:
        app.logger.warning("Price lookup failed for %s: %s", code, error)
    return None

@app.route("/price/<code>")
def price(code):
    code = code.strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{6}", code):
        return jsonify({"error": "Invalid stock code"}), 400
    p = get_price(code)
    if p:
        return jsonify({"code": code, "price": p})
    return jsonify({"error": "가격을 가져올 수 없습니다"}), 502

@app.route("/prices")
def prices():
    codes = list(dict.fromkeys(code.strip().upper() for code in request.args.get("codes", "").split(",") if code.strip()))
    if not codes or len(codes) > 30 or any(not re.fullmatch(r"[0-9A-Z]{6}", code) for code in codes):
        return jsonify({"error": "Provide 1 to 30 valid stock codes"}), 400
    with ThreadPoolExecutor(max_workers=6) as executor:
        result = dict(zip(codes, executor.map(get_price, codes)))
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response, 200 if all(value is not None for value in result.values()) else 502

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
