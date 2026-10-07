# Mopolee WhatsApp AI Setup

This is a simple WhatsApp webhook server for the Mopolee dashboard.

## What it does

- receives WhatsApp messages from Twilio
- sends the message to OpenAI
- replies through the same WhatsApp number

## Required services

1. Twilio WhatsApp Business account
2. OpenAI API key
3. A public URL for the webhook (for example, via ngrok)

## 1. Install dependencies

pip install -r requirements.txt

## 2. Configure environment

Copy `.env.example` to `.env` and fill in the real values.

## 3. Run the server

python whatsapp_ai_server.py

## 4. Expose it to the internet

Use ngrok:

ngrok http 8082

Then set Twilio webhook to:

https://your-ngrok-url/webhook

## 5. Twilio webhook configuration

In your Twilio console:

- go to Messaging > WhatsApp Senders
- configure webhook for incoming messages
- set the URL to the webhook endpoint

## 6. Test

Send a WhatsApp message to your Twilio number, for example:

Hello Mopolee AI

The bot should reply with an AI-generated message.

## Notes

- Replace the default placeholder values with your real credentials.
- This project is a starter integration; it is not production-secured yet.
- Add auth, logging, and message validation before going live.
