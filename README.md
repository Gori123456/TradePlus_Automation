# TradePlus Automation

## Overview

TradePlus Automation is a Python-based desktop automation project designed to automate repetitive tasks within the TradePlus application. The project uses Windows UI automation techniques to interact with application controls, navigate menus, process records, and perform operational workflows with minimal manual intervention.

## Features

* Automated login functionality
* Menu navigation automation
* Process button identification and execution
* Dynamic control handling
* Configuration-driven execution using JSON files
* Logging and status tracking
* Error handling and recovery mechanisms
* Scalable architecture for additional TradePlus workflows

## Technologies Used

* Python
* Pywinauto
* JSON Configuration
* Windows UI Automation (UIA)

## Project Structure

```
TradePlus_Automation/
│
├── app.py
├── config.json
├── requirements.txt
├── logs/
├── modules/
├── utils/
└── README.md
```

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
```

2. Navigate to the project directory:

```bash
cd TradePlus_Automation
```

3. Create a virtual environment:

```bash
python -m venv venv
```

4. Activate the virtual environment:

```bash
venv\Scripts\activate
```

5. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Update the `config.json` file with the required application path and execution parameters before running the automation.

## Running the Application

```bash
python app.py
```

## Version History

### v1.0

* Initial project setup
* TradePlus application launch automation
* Login automation
* Menu navigation implementation
* Process execution workflow
* Configuration management using JSON

## Future Enhancements

* Advanced control recognition
* Automated report generation
* Database integration
* Email notifications
* Enhanced logging dashboard

## Author

Jatin Gori

## License

This project is intended for internal automation and learning purposes.
