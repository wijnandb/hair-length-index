# Monetization Ideas

## Fan Upload Feature (GIF + 6-tier progression)

**Concept:** Fan uploads selfie in team jersey → we generate 6 hair tiers using AI → they get a GIF of their "hair growing" as their team fails to win 5 in a row.

**Pricing:**
- Free: 1 image (current tier), watermarked
- Paid (€1-2): All 6 tiers + animated GIF, no watermark
- Premium (€5): Custom video (Remotion) with their face in head-to-head format

**COGS:** 6 images × $0.04 = $0.24 per customer
**Margin:** ~75-88%

**Viral loop:** Every fan who generates wants to share → brings more fans → some pay

**Implementation:**
- Cloudflare Worker or simple server endpoint
- Stripe Checkout for payment (one-time, no subscription)
- Queue system: upload → generate → email/download link
- Storage: Cloudflare R2 or GitHub releases

**When to build:** After proving organic engagement with AI-generated images in posts.

## Sponsorship / Partnership

Once the index has visibility:
- Betting companies (hair length as odds indicator?)
- Barber shops (partnership: "when your team gets a haircut, get 10% off at...")
- Football media (licensed data/visualizations)

## Merchandise

- "I survived [X] days" t-shirts for specific teams
- "Sasquatch supporter" hoodies
- Print-on-demand, no inventory
