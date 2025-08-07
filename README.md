# AskMaven AI Backend

This is the backend service for the **AskMaven AI** chatbot. It uses **FastAPI** for the API and **Google Gemini** for AI processing. The system scrapes websites, extracts entities, and provides intelligent responses based on the content.

## Features
- Web scraping with 15 extraction methods
- Entity extraction for people, companies, roles, and more
- Intelligent Q&A system powered by Google Gemini
- User management with JWT authentication

## Installation
1. Clone this repository: `git clone https://github.com/yourusername/UrlChatbotBackend.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the app: `uvicorn main:app --reload`

## Contributing
Contributions are welcome! Please fork the repository, create a branch, and submit a pull request.
