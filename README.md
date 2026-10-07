# Mopolee AI Dashboard

Mopolee is an authenticated cinema and exchange demo with responsive dashboard, per-account profile, saved appearance settings, and a free sign-in-required film preview.

## Project files

- index.html — main dashboard markup
- styles.css — dashboard styling and theme
- script.js — UI interactions, nav switching, and payment simulation logic

## What it includes

- Sidebar navigation with active states
- Overview dashboard with KPI cards
- Revenue chart area
- Customer insights panel
- Campaign table
- Quick action widgets
- Cinema, Exchange, Wallet, Rewards, Tickets sections
- Signed-in personal profile and browser-saved color themes
- A share button using the platform share sheet or a copyable demo URL
- Free film preview served only to signed-in accounts

## Run locally

The full authenticated application runs through Flask. From the project folder:

1. Install the Python dependencies:

   python -m pip install -r requirements.txt

2. Start the Flask app:

   python whatsapp_ai_server.py

Then open `http://127.0.0.1:8082`. To use the app on a phone, connect it and the computer to the same Wi-Fi, find the computer's IPv4 address with `ipconfig`, and open `http://<computer-ip>:8082` on the phone. The server binds to the local network; allow it through Windows Firewall on private networks only. Opening `index.html` directly or using `python -m http.server` only previews the static design; authentication, the shared film catalogue, and uploads require Flask.

## Important prototype note

Cinema booking, wallet actions, and payments are still demonstrations and are not connected to live services.

## Design intent

The style is a premium dark mode interface with glassmorphism panels, neon accents, and a modern fintech/cinema dashboard feel.

## Current status

The dashboard is served through Flask for authenticated users. The Cinema library supports a local free demo film behind sign-in and optional owner-only publishing with Cloudflare R2. R2 uploads go directly from the browser to a private bucket using short-lived signed URLs. R2 credentials stay on the server, and viewers must sign in to receive temporary playback links. Wallet amounts, booking, and viewing-reward payouts are still examples and do not move real money.

The Render blueprint is set to allow public account registration for a shareable demo; film viewing still requires sign-in. A public HTTPS link is not live until the app is deployed from a connected Git repository and a persistent production database is configured.

To promote the app, run Flask and share its HTTPS address using **Share Mopolee**. The sign-in page includes social-preview metadata and the cinema artwork. The layout adapts to phone and desktop browsers; app-store listings and deployment to each platform still require their own publishing process.

## Social promo videos

The `promo/` folder contains a 24-second vertical video for phone-first social feeds, a widescreen video for landscape players, and a thumbnail. The videos use captions inside high-contrast safe-area bars. Only post the supplied film footage publicly if you have the rights to distribute it.

## Suggested next engineering tasks

- Replace placeholder payment keys with real credentials
- Connect dashboard metrics to real backend APIs
- Add real cinema booking data and exchange rate logic
- Hook wallet, rewards, and tickets screens to live services
- Add legally licensed or public-domain films to the collection

## Configure the online Cinema library

1. Create a private Cloudflare R2 bucket and an R2 API token scoped to that bucket with object read/write access.
2. Configure `CATALOG_ADMIN_EMAIL` with the email address of the account allowed to publish films.
3. Set `CLOUDFLARE_R2_ACCOUNT_ID`, `CLOUDFLARE_R2_BUCKET`, `CLOUDFLARE_R2_ACCESS_KEY_ID`, and `CLOUDFLARE_R2_SECRET_ACCESS_KEY` in the server environment. For local testing, keep these values in the ignored `.env` file; for Render, add them as service environment variables. Never put R2 secrets in browser code or commit them.
4. In the R2 bucket's **Settings → CORS Policy**, allow your exact app origin (for example `http://localhost:8082` and the deployed app origin), methods `GET`, `HEAD`, and `PUT`, and headers `Content-Type` and `Range`. Expose `ETag`, `Content-Length`, `Accept-Ranges`, and `Content-Range`.
5. Run and open the Flask app, sign in with the configured catalogue-owner account, then use **Cinema → Add a film**. Only MP4 video is accepted (up to 4.5 GB); an optional JPG, PNG, or WebP poster can be up to 10 MB.

The owner-only upload form appears only for the configured catalogue account. Published titles appear for all signed-in viewers. Keep the bucket private; the app creates temporary signed playback and poster URLs. Browser uploads and playback require the bucket CORS policy. Actual R2 connectivity still needs to be verified after configuring the Cloudflare account and server secrets.
