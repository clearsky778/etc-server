from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
CORS(app)

def get_price(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        price = soup.select_one(".no_today .blind")
        if price:
            return int(price.text.replace(",", ""))
    except:
        pass
    return None

@app.route("/price/<code>")
def price(code):
    p = get_price(code)
    if p:
        return jsonify({"code": code, "price": p})
    return jsonify({"error": "가격을 가져올 수 없습니다"}), 400

@app.route("/prices")
def prices():
    codes = request.args.get("codes", "").split(",")
    result = {}
    for code in codes:
        code = code.strip()
        if code:
            p = get_price(code)
            result[code] = p
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
