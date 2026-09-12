from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

def get_quote(code):
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
        traded_at = None
        try:
            stamp = datetime.fromisoformat(data.get("localTradedAt", ""))
            if stamp.tzinfo is not None and stamp <= datetime.now(timezone.utc):
                traded_at = stamp.isoformat()
        except (ValueError, TypeError):
            pass
        return {"price": int(raw), "asOf": traded_at, "marketStatus": data.get("marketStatus")}
    except (requests.RequestException, ValueError) as error:
        app.logger.warning("Price lookup failed for %s: %s", code, error)
    return None

def get_price(code):
    quote = get_quote(code)
    return quote["price"] if quote else None

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
        quotes = dict(zip(codes, executor.map(get_quote, codes)))
    result = {code: quote["price"] if quote else None for code, quote in quotes.items()}
    # Keep the legacy response for already-installed calculators.
    if request.args.get("details") == "1":
        stamps = [quote.get("asOf") if quote else None for quote in quotes.values()]
        as_of = min(stamps, key=datetime.fromisoformat) if all(stamps) else None
        statuses = {quote.get("marketStatus") for quote in quotes.values() if quote}
        result = {"prices": result, "quotes": quotes, "asOf": as_of,
                  "marketStatus": next(iter(statuses)) if len(statuses) == 1 else None}
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response, 200 if all(quote is not None for quote in quotes.values()) else 502

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
