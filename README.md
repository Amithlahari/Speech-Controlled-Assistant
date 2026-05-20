# A.N.J.A — Voice-Driven Intelligent Assistant

A.N.J.A (Autonomous Nursing & Job Assistant) is a voice-driven intelligent assistant prototype designed for assistive robotic interaction in constrained medical environments such as catheterization laboratories.

The project focuses on reliable speech-based interaction, real-time system feedback, and safety-oriented command execution using offline speech recognition and modular command validation workflows.

---

## Features

- Offline speech recognition using Faster Whisper
- Wake-word-based interaction system
- Real-time WebSocket communication
- Voice-controlled robotic action simulation
- Confirmation-gated command execution
- Fuzzy matching for medical tools and commands
- Continuous audio listening pipeline
- Interactive monitoring dashboard UI
- Safety-oriented emergency stop handling
- Manual command injection through UI

---

## System Architecture

The system consists of:

1. Speech Recognition Pipeline
2. Command Parsing & Normalization
3. Confidence & Validation Logic
4. Real-Time WebSocket Communication
5. Interactive Dashboard UI
6. Simulated Robot Action Layer

---

## Technologies Used

### Backend
- Python
- Asyncio
- WebSockets
- Faster Whisper
- RapidFuzz
- NumPy
- SoundDevice
- SciPy

### Frontend
- HTML
- CSS
- JavaScript

---

## Project Structure

```text
ANJA-Voice-Assistant/
│
├── images/
├── models/
│
├── anja_backend.py
├── robot_ui.html
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Setup Instructions

### 1. Clone Repository

```bash
git clone https://github.com/Amithlahari/ANJA-Voice-Assistant.git
cd ANJA-Voice-Assistant
```

---

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Run Backend

```bash
python anja_backend.py
```

Backend starts on:

```text
ws://localhost:8765
```

---

### 4. Launch Frontend

Open:

```text
robot_ui.html
```

in your browser.

---

## Example Commands

```text
anja bring gauze
anja bring scalpel
anja hold
anja idle
freeze
confirm
cancel
```

---

## Safety Features

- Emergency freeze command
- Confirmation-gated execution
- Pending action timeout
- Wake-word validation
- Unknown command rejection
- Real-time status updates

---

## Motivation

This project was developed during the CathBot Hackathon to explore intelligent voice-interaction systems for assistive robotic workflows in medical environments where hands-free interaction and reliability are critical.

The focus was on:
- human-computer interaction,
- reliable speech interfaces,
- modular software workflows,
- and intelligent command validation.

---

## Future Improvements

- Improved NLP understanding
- Better noise robustness
- Vision system integration
- Real robotic hardware integration
- Deployment optimization
- Model quantization and edge deployment
- Better frontend modularization

---

## Disclaimer

This project is a research and prototyping effort intended for educational and experimental purposes only. It does not control real medical hardware.

---

## Author

Amith S Lahari

GitHub:
https://github.com/Amithlahari