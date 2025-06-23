# 💊 HealthCare-AI — AI-Powered Healthcare Web App 🧠

**HealthCare-AI** is a smart and user-friendly healthcare assistant web application built using **Flask** and integrated with **Gemini API**. It offers a full suite of tools to empower users to monitor their health, get AI-driven assistance, and manage medical routines with ease.

---

## 🚀 Features

### 🤖 AI Services
- **Symptom Checker** – Enter symptoms to get AI-predicted possible conditions.
- **AI Health Assistant** – Gemini-powered chatbot to answer health-related queries.
- **Health Tips & Reviews** – Get daily AI-generated health tips and explore user reviews.

### 🧰 Health Tools
- **BMI Calculator** – Compute Body Mass Index (BMI) using height and weight.
- **Pill Reminder** – Set reminders to take medications on time.
- **Mental Health Support** – Access supportive resources and AI-based emotional help.

### 🏥 Healthcare Services
- **Appointments** – Book medical appointments via a simple interface.
- **Blood Donation** – Connect with donors and recipients in need.
- **Insurance Info** – AI-curated guidance and FAQs on health insurance policies.

### 🔐 Admin Panel
- Role-based access control: admin and users.
- Manage user privileges and moderate content.
- Monitor activity logs and feature usage.

---

## 🛠️ Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, Bootstrap
- **AI Integration**: Gemini API
- **Database**: SQLite
- **Authentication**: Flask-Login with role management
- **Task Scheduling**: Cron jobs for pill reminders

---

## 📦 Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/ad1lhasan/HealthCare-AI.git
cd HealthCare-AI
```
### 2. Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # For Windows: venv\Scripts\activate
```

### 3. Install all dependencies
```bash
pip install -r requirements.txt
```
### 4. Add your Gemini API key
Create a file named config.py and add the following line:
```
GEMINI_API_KEY = "your_gemini_api_key_here"
```

### 5. Run the application
```
python app.py
```
## 🧠 Gemini API Integration
This project uses Gemini AI to:

*  Provide real-time responses in the chatbot

*  Analyze symptoms and suggest potential conditions

*  Summarize and generate health content

*  Answer health insurance–related queries

Make sure you have access to Gemini and set up your API key as instructed above.

## 📁 Project Structure
```
HealthCare-AI/
├── app.py                 # Main Flask app
├── config.py              # API key configuration
├── static/                # CSS, images, JS
├── templates/             # HTML files
├── requirements.txt       # Dependencies
└── README.md              # Project info
```
## 🤝 Contribution
Contributions are welcome! Here's how you can help:

*  Fork the repository

*  Create a new branch for your feature or fix

*  Push your changes

*  Submit a pull request

You can also open an issue for suggestions or bugs.


## 📜 License
This project is licensed under the MIT License.
Feel free to use, modify, and share with credit.

🙏 Acknowledgements
*  Gemini API – for powering the AI functionality

*  Flask – lightweight Python web framework
  
*  Bootstrap – for responsive UI design
  
*  All testers, contributors, and users who gave feedback

## 📬 Contact
Author: Muhammed Adil Hasan

Email: muhammedadilhasan@gmail.com

GitHub: ad1lhasan

