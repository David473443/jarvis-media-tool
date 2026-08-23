# J.A.R.V.I.S Media Generator

Generate AI images and videos from text prompts.

## What works FREE right now (no key)
- **Images**: Pollinations (unlimited, no signup, no key). Just type a prompt.

## What needs a FREE key (sign up, no card)
- **Video (MiniMax H3)**: get a free key at https://platform.minimax.io -> API keys.
  Put it in `.env` as `MINIMAX_API_KEY=...`
- **Video (fal.ai)**: get a free key at https://fal.ai/dashboard -> keys.
  Put it in `.env` as `FAL_KEY=...`

## Run
```
pip install -r requirements.txt
python3 app.py
```
Open http://localhost:5000

## Endpoints
- POST /api/image  {prompt, width, height}        -> returns image URL (Pollinations)
- POST /api/video  {prompt, model:"minimax|fal", duration} -> returns video URL
