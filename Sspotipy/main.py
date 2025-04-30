import os

from flask import app

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Dynamically use Railway's port
    app.run(host='0.0.0.0', port=port, debug=True)
