# Guppy: Credentials & API Keys Guide
**Last Updated:** 2026-04-22  
**Purpose:** Quick reference for all credentials and API keys needed for Guppy

---

## TL;DR - What You Need

For a **fully-featured** Guppy setup:

| Service | API Key | Priority | Cost | Where to Get |
|---------|---------|----------|------|--------------|
| **Local Models** | None | 🔴 Required | Free | Ollama (`ollama.ai`) |
| **Claude (Anthropic)** | `sk-ant-*` | 🟡 Optional | Pay-as-you-go | https://console.anthropic.com |
| **ChatGPT (OpenAI)** | `sk-*` | 🟡 Optional | Pay-as-you-go | https://platform.openai.com |
| **Gemini (Google)** | API Key | 🟡 Optional | Free tier available | https://aistudio.google.com |
| **Premium Voice (ElevenLabs)** | API Key | 🟡 Optional | Free tier (10K/mo) | https://elevenlabs.io |

**Minimum Setup:** Only Ollama is required. Everything else is optional cloud providers.

---

## Detailed Setup Guide

### 1. LOCAL MODELS (REQUIRED)

#### Ollama
- **What:** Local LLM inference engine
- **Why Required:** Guppy runs models locally, no API key needed
- **Where:** https://ollama.ai
- **Setup Time:** 5 minutes
- **Cost:** Free
- **Install:**
  ```powershell
  # Download installer from https://ollama.ai
  # Run installer, follow prompts
  # Start Ollama
  ollama serve
  
  # In another terminal, pull a model
  ollama pull qwen2.5:7b
  ```
- **Verify:**
  ```powershell
  curl http://127.0.0.1:11434/api/tags
  # Should see: qwen2.5:7b in response
  ```

---

### 2. CLOUD LLM PROVIDERS (OPTIONAL)

#### Anthropic (Claude)
- **URL:** https://console.anthropic.com/account/keys
- **Sign Up Time:** 5 minutes
- **Cost:** 
  - No upfront charge
  - Pay-as-you-go: ~$0.003 per 1K input tokens, $0.015 per 1K output tokens
  - Claude 3.5 Sonnet (recommended): Accurate, fast, reasonably priced
- **Get API Key:**
  1. Go to https://console.anthropic.com/account/keys
  2. Click "Create Key"
  3. Copy the key (starts with `sk-ant-v0-`)
  4. Save in Guppy Settings → Anthropic
- **Key Format:** `sk-ant-v0-...` (long string)
- **Testing:**
  ```bash
  curl https://api.anthropic.com/v1/messages \
    -H "x-api-key: sk-ant-v0-..." \
    -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":100,"messages":[{"role":"user","content":"Hi"}]}'
  ```
- **Pricing Tier Recommendation:**
  - Individual ($0): Start here, excellent for testing
  - Small Business: If you hit limits
  - Enterprise: Large-scale deployments

#### OpenAI (GPT)
- **URL:** https://platform.openai.com/account/api-keys
- **Sign Up Time:** 10 minutes
- **Cost:**
  - Requires credit card
  - GPT-4 Turbo: ~$0.01 per 1K input, $0.03 per 1K output
  - GPT-4o mini: ~$0.00015 per 1K input, $0.0006 per 1K output (cheap!)
- **Get API Key:**
  1. Sign up at https://openai.com
  2. Go to https://platform.openai.com/account/api-keys
  3. Click "Create new secret key"
  4. Copy the key (starts with `sk-`)
  5. Save in Guppy Settings → OpenAI
- **Key Format:** `sk-...` (long string)
- **Testing:**
  ```bash
  curl https://api.openai.com/v1/chat/completions \
    -H "Authorization: Bearer sk-..." \
    -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hi"}]}'
  ```
- **Pricing Tier:** Standard (Free to use with pay-as-you-go)

#### Google (Gemini)
- **URL:** https://aistudio.google.com/app/apikey
- **Sign Up Time:** 5 minutes
- **Cost:**
  - Free tier: 2 million requests/month (very generous)
  - Paid tier: ~$0.05-0.15 per 1M input tokens
- **Get API Key:**
  1. Go to https://aistudio.google.com
  2. Click "Get API Key"
  3. Create a new API key in Google Cloud
  4. Copy the key
  5. Save in Guppy Settings → Google
- **Key Format:** Usually long alphanumeric (e.g., `AIza...`)
- **Testing:**
  ```bash
  curl https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=YOUR_API_KEY \
    -d '{"contents":[{"parts":[{"text":"Hi"}]}]}'
  ```
- **Pricing Tier:** Generous free tier (start here!)

---

### 3. VOICE SERVICES (OPTIONAL)

#### ElevenLabs (Premium Voice Synthesis)
- **URL:** https://elevenlabs.io/account/account
- **Sign Up Time:** 5 minutes
- **Cost:**
  - Free tier: 10,000 characters/month
  - Starter: $5/month (100K characters)
  - Professional: $99/month (1M characters)
- **Get API Key:**
  1. Sign up at https://elevenlabs.io
  2. Go to https://elevenlabs.io/account/account
  3. Scroll to "API Keys"
  4. Copy the key
  5. Save in Guppy Settings → Voice → TTS
- **Key Format:** Alphanumeric string
- **Use Case:** High-quality voice output for chat responses
- **Testing:**
  ```bash
  curl https://api.elevenlabs.io/v1/voices \
    -H "xi-api-key: YOUR_API_KEY"
  ```

---

## Credential Storage in Guppy

### How Guppy Stores Credentials

1. **Encryption:** All API keys are encrypted using AES-256
2. **Storage:** Encrypted keys stored in `credentials` table
3. **Keyring:** Uses Windows DPAPI when available (automatic)
4. **Access:** Only decrypted when needed for API calls
5. **Never Logged:** Keys never appear in logs or console

### Adding Credentials to Guppy

**Via Web UI:**
1. Open http://localhost:3000
2. Click "Settings" → "Providers"
3. For each provider you want to use:
   - Enter API Key
   - Click "Save"
   - Click "Activate" to use as default

**Via API:**
```bash
curl -X POST http://localhost:8000/api/settings/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "anthropic",
    "api_key": "sk-ant-v0-..."
  }'
```

### Credential Security Checklist

- ✅ Never commit API keys to Git
- ✅ Never paste keys in console/chat
- ✅ Never share keys in screenshots
- ✅ Rotate keys regularly (~quarterly)
- ✅ Use different keys for different environments (dev vs prod)
- ✅ Monitor API key usage in provider dashboards
- ✅ Delete unused/old keys immediately

---

## Setting Up Each Provider (Step-by-Step)

### Setup 1: Anthropic (Claude)
**Time: 10 minutes**

```
1. Go to https://console.anthropic.com
2. Click "Sign up" (or "Log in" if existing account)
3. Enter email/password
4. Verify email
5. Go to https://console.anthropic.com/account/keys
6. Click "Create Key"
7. Name it "Guppy" (or whatever)
8. Copy the key: sk-ant-v0-...
9. Open Guppy Web UI (http://localhost:3000)
10. Settings → Providers → Anthropic
11. Paste key in "API Key" field
12. Click "Save"
13. Click "Activate"
14. Done!
```

### Setup 2: OpenAI (ChatGPT)
**Time: 15 minutes**

```
1. Go to https://openai.com
2. Click "Sign up"
3. Enter email/password (or use Google/Microsoft login)
4. Verify email
5. Add payment method (credit card required)
6. Go to https://platform.openai.com/account/api-keys
7. Click "Create new secret key"
8. Name it "Guppy"
9. Copy the key: sk-...
10. Save safely (can't be viewed again!)
11. Open Guppy Web UI
12. Settings → Providers → OpenAI
13. Paste key
14. Click "Save"
15. Click "Activate"
16. Done!
```

### Setup 3: Google (Gemini)
**Time: 10 minutes**

```
1. Go to https://aistudio.google.com
2. Click "Get API Key"
3. Click "Create API key in Google Cloud"
4. Select or create a project
5. Create API key
6. Copy the key
7. Go back to https://aistudio.google.com
8. Paste key to verify it works
9. Open Guppy Web UI
10. Settings → Providers → Google
11. Paste key
12. Click "Save"
13. Click "Activate"
14. Done!
```

### Setup 4: ElevenLabs (Premium Voice)
**Time: 10 minutes**

```
1. Go to https://elevenlabs.io
2. Click "Sign up"
3. Enter email/password
4. Verify email
5. Go to https://elevenlabs.io/account/account
6. Scroll to "API Keys"
7. Copy the key
8. Open Guppy Web UI
9. Settings → Voice Settings
10. Select "ElevenLabs" as TTS provider
11. Paste API key
12. Select voice (e.g., "Alloy")
13. Test audio (click play button)
14. Done!
```

---

## Cost Estimation

### Scenario 1: Budget Setup (Local Only)
- **Monthly Cost:** $0
- **Use Case:** Personal use, offline
- **Includes:** Local models via Ollama
- **Model Quality:** Good (Qwen 7B, CodeLlama)

### Scenario 2: Hybrid Setup (Local + Claude)
- **Monthly Cost:** $5-50 (depends on usage)
- **Claude Pricing:** ~$0.003 input, $0.015 output per 1K tokens
- **Estimated Usage (Light):** 10 conversations/day = ~$5/month
- **Estimated Usage (Medium):** 50 conversations/day = ~$25/month
- **Estimated Usage (Heavy):** 200 conversations/day = ~$100/month
- **Recommendation:** Set billing alerts in Anthropic console

### Scenario 3: Full Setup (Local + Claude + OpenAI + Google)
- **Monthly Cost:** $5-100+
- **Why Multiple?** Redundancy, cost optimization, testing
- **Google:** Free tier usually sufficient
- **OpenAI:** GPT-4o mini is cheap (~$0.15/day for light use)
- **Claude:** Best for reasoning tasks
- **Recommendation:** Use Claude for complex tasks, OpenAI for simple tasks

---

## Credential Format Reference

### What NOT to Do
❌ `anthropic: sk-ant-v0-xxx` (in config file)
❌ Paste key in code comments
❌ Save key in browser autocomplete
❌ Share key via email/chat

### What TO Do
✅ Save key in Guppy Settings (encrypted)
✅ Save key in 1Password/KeePass (password manager)
✅ Regenerate keys regularly
✅ Use separate keys per environment

---

## Troubleshooting

### "Invalid API Key" Error
1. Check key hasn't been revoked in provider console
2. Verify you copied the entire key (not truncated)
3. Check key format matches provider (e.g., `sk-ant-` for Anthropic)
4. Try generating a new key in provider console
5. Clear browser cache and retry

### "Rate Limit Exceeded" Error
1. Provider is throttling you (too many requests)
2. Check your usage in provider dashboard
3. Wait a bit and retry
4. Consider upgrading plan if chronic

### "Quota Exceeded" Error
1. You've hit your monthly limit
2. Check billing status in provider console
3. Either wait until next month or add payment method
4. For Google Gemini, free tier resets monthly

### Credentials Not Saving
1. Check browser console for errors (F12)
2. Verify API is running (`curl http://localhost:8000/api/health`)
3. Check database isn't corrupted
4. Try in incognito window (rules out browser cache)
5. Check Windows Firewall isn't blocking

---

## Creating Test Keys

Some providers support sandbox/test keys:

**Anthropic:**
- No sandbox, but can use `claude-3-5-haiku` (cheapest model) for testing
- Cost: $0.00050 input, $0.0015 output per 1K tokens

**OpenAI:**
- No sandbox, but can use `gpt-4o-mini` for cheap testing
- Cost: $0.00015 input, $0.0006 output per 1K tokens

**Google:**
- Free tier = test environment
- 2 million requests/month is very generous

---

## Best Practices

1. **Rotation:** Rotate keys every 3-6 months
2. **Monitoring:** Check provider dashboards weekly for unexpected charges
3. **Alerts:** Set up billing alerts in each provider
4. **Cleanup:** Delete old keys you're not using
5. **Documentation:** Keep track of which keys are used for what
6. **Backup:** If using Guppy on multiple devices, you'll need to add credentials separately to each

---

## FAQ

**Q: Can I use the same key on multiple devices?**
A: Yes, but you'll need to add it to each device's Guppy installation. The key is encrypted locally, so each device has its own copy.

**Q: What if I lose my key?**
A: Most providers let you regenerate keys in the console. If you can't, create a new one and delete the old one.

**Q: Do I have to use cloud providers?**
A: No! Ollama (local) is fully functional. Cloud providers are optional for:
- Better model quality
- Specific model capabilities (Claude's reasoning)
- Fallback if local model is overloaded

**Q: How much will this cost?**
A: For personal use: $0-50/month depending on which providers you use.

**Q: Is my key secure?**
A: Yes, Guppy encrypts all keys. Even if the database was stolen, keys would still be encrypted. But treat them like passwords - don't share them.

**Q: Can I use organizational/team API keys?**
A: Yes, but you'll be responsible for any costs. Consider using separate personal keys for different projects.

