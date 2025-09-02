# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI sales consultant (amber_ai_consultant) that integrates multiple services to provide automated customer support with human escalation capabilities. The system is designed to handle customer inquiries and escalate complex situations to human staff.

## Service Integrations

The project integrates with several external services:

- **OpenAI API**: Core AI functionality for natural language processing
- **МойСклад (MoySklad)**: Russian inventory management system for product/service data
- **Telegram Bot**: Customer communication interface 
- **Telegram User API**: Advanced userbot functionality
- **AmoCRM**: Customer relationship management
- **YuKassa**: Payment processing system

## Environment Configuration

All API keys and sensitive configuration are stored in `.env` file. Key services configured:

- `OPENAI_API_KEY` and `OpenAI_BASE_URL` for AI responses
- `MOYSKLAD_TOKEN`, `MOYSKLAD_LOGIN`, `MOYSKLAD_PASSWORD` for inventory access
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` for Telegram integration
- `AMOCRM_*` variables for CRM integration
- `YUKASSA_*` variables for payment processing

## Development Setup

This project uses Python with virtual environment:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (when requirements.txt is created)
pip install -r requirements.txt
```

## Architecture Notes

The system is designed with these core components:
- AI-powered conversation handling using OpenAI API
- Product/service database integration via МойСклад API
- Multi-channel communication (Telegram Bot and User API)
- CRM integration for customer data management
- Payment processing capabilities
- Conversation logging for all customer interactions

## AI Generation Parameters

The AI responses should use these parameters for consistency:
- `temperature=0.7` - Balance of creativity and accuracy
- `max_tokens=500` - Response length limit
- `presence_penalty=0.6` - Encourages topic diversity
- `frequency_penalty=0.5` - Reduces word repetition

## Development Workflow

The project is intended to be connected to remote repository: `git@github.com:Dmitrii-VO/RomanProject.git`

Remember to:
1. Keep `.env` file in `.gitignore` to protect sensitive information
2. Maintain conversation logs for all customer interactions
3. Implement proper error handling for service integrations
4. Create and maintain Project Knowledge Map for system documentation