from flask import Flask, request, jsonify
import requests
import re
from datetime import datetime, timedelta
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow frontend (Lovable React) to call backend

FRANKFURTER_URL = "https://api.frankfurter.app"

# -----------------------
# /convert endpoint
# -----------------------
@app.route('/convert', methods=['GET'])
def convert_currency():
    amount = request.args.get('amount', type=float)
    from_currency = request.args.get('from', default="USD", type=str).upper()
    to_currency = request.args.get('to', default="INR", type=str).upper()

    if not amount:
        return jsonify({"error": "Missing amount"}), 400

    url = f"{FRANKFURTER_URL}/latest"
    params = {"amount": amount, "from": from_currency, "to": to_currency}
    res = requests.get(url, params=params).json()

    converted = res["rates"].get(to_currency)
    rate = converted / amount if amount and converted else None

    return jsonify({
        "from": from_currency,
        "to": to_currency,
        "amount": amount,
        "converted": converted,
        "rate": rate
    })



@app.route('/historical', methods=['GET'])
def historical_data():
    from_currency = request.args.get('from', default="USD", type=str).upper()
    to_currency = request.args.get('to', default="INR", type=str).upper()
    range_param = request.args.get('range', default="7d", type=str).lower()

    end_date = datetime.now().date()

    if range_param in ["7d", "7days"]:
        start_date = end_date - timedelta(days=7)
    elif range_param in ["30d", "1m", "30days"]:
        start_date = end_date - timedelta(days=30)
    elif range_param in ["365d", "1y", "year"]:
        start_date = end_date - timedelta(days=365)
    elif range_param in ["all", "max"]:
        start_date = datetime(1999, 1, 4).date()
    else:
        return jsonify({"error": "Invalid range. Use 7d, 30d/1m, 365d/1y, or all/max"}), 400

    url = f"{FRANKFURTER_URL}/{start_date.isoformat()}..{end_date.isoformat()}"
    params = {"from": from_currency, "to": to_currency}
    res = requests.get(url, params=params).json()

    if "rates" not in res:
        return jsonify({"error": "No data available"}), 404

    dates = []
    rates = []

    # Sort and sample large datasets
    sorted_data = sorted(res["rates"].items())
    step = max(1, len(sorted_data) // 100)  # keep max 100 points

    for i, (date, data) in enumerate(sorted_data):
        if i % step == 0:  # sample points
            dates.append(date)
            rates.append(data[to_currency])

    return jsonify({
        "from": from_currency,
        "to": to_currency,
        "range": range_param,
        "dates": dates,
        "rates": rates
    })



@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    message = data.get("message", "").lower().strip()

    # -----------------------------------
    # 1. Match conversion queries
    # -----------------------------------
    match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z]{2,}|rupee|yen|dollar|euro)\s*(?:to|in)?\s*([a-zA-Z]{2,}|rupee|yen|dollar|euro)", message)
    if match:
        amount, from_currency, to_currency = match.groups()

        mapping = {
            "rupee": "INR",
            "yen": "JPY",
            "dollar": "USD",
            "euro": "EUR",
            "pound": "GBP"
        }
        from_currency = mapping.get(from_currency.lower(), from_currency.upper())
        to_currency = mapping.get(to_currency.lower(), to_currency.upper())

        url = f"{FRANKFURTER_URL}/latest"
        params = {"amount": float(amount), "from": from_currency, "to": to_currency}
        res = requests.get(url, params=params).json()

        if "rates" in res and to_currency in res["rates"]:
            converted = res["rates"][to_currency]
            return jsonify({
                "response": f"{amount} {from_currency} = {converted} {to_currency}",
                "converted": converted,
                "rate": converted / float(amount)
            })

    # -----------------------------------
    # 2. Specific date queries
    # -----------------------------------
    match = re.search(r"(usd|eur|inr|jpy|gbp|[a-zA-Z]{3})\s*(?:to)?\s*(usd|eur|inr|jpy|gbp|[a-zA-Z]{3}).*on\s*(\d{4}-\d{2}-\d{2})", message)
    if match:
        from_currency, to_currency, date = match.groups()
        from_currency, to_currency = from_currency.upper(), to_currency.upper()

        url = f"{FRANKFURTER_URL}/{date}"
        params = {"from": from_currency, "to": to_currency}
        res = requests.get(url, params=params).json()

        if "rates" in res and to_currency in res["rates"]:
            rate = res["rates"][to_currency]
            return jsonify({
                "response": f"💱 On {date}, 1 {from_currency} = {rate} {to_currency}",
                "rate": rate,
                "date": date
            })

    # -----------------------------------
    # 3. Historical range queries
    # -----------------------------------
    match = re.search(r"(usd|eur|inr|jpy|gbp|[a-zA-Z]{3})\s*to\s*(usd|eur|inr|jpy|gbp|[a-zA-Z]{3}).*last\s*(\d+)\s*days", message)
    if match:
        from_currency, to_currency, days = match.groups()
        from_currency, to_currency = from_currency.upper(), to_currency.upper()
        days = int(days)

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        url = f"{FRANKFURTER_URL}/{start_date.isoformat()}..{end_date.isoformat()}"
        params = {"from": from_currency, "to": to_currency}
        res = requests.get(url, params=params).json()

        if "rates" in res:
            return jsonify({
                "response": f"📊 Showing {from_currency} → {to_currency} for last {days} days",
                "data": res["rates"]
            })

    # -----------------------------------
    # Default fallback
    # -----------------------------------
    return jsonify({"response": "❓ I didn't understand. Try: 'Convert 100 USD to INR', 'Rate of USD to INR on 2023-01-05', or 'USD to EUR last 30 days'."})


if __name__ == "__main__":
    print("🚀 Starting Flask server...")
    app.run(debug=True)
