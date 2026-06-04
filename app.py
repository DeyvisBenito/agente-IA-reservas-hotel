import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from hotel import process_message

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route('/nwl-x7k2-chat', methods=['POST'])
def chat():
    data = request.json
    session_id = data.get('session_id', 'default')
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'error': 'Mensaje vacío'}), 400

    result = process_message(session_id, user_message)
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)