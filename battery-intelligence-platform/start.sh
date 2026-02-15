
#!/bin/bash
echo "🚀 Starting VoltAI Platform..."

# Check for Node
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed."
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed."
    exit 1
fi

echo "📦 Installing Backend Dependencies..."
pip install -r requirements.txt

echo "🎨 Installing Frontend Dependencies..."
cd frontend
npm install
cd ..

echo "✅ Setup Complete!"
echo "To run the backend: uvicorn backend.app.main:app --reload"
echo "To run the frontend: cd frontend && npm run dev"
