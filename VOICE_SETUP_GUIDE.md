# 🎤 GUPPY VOICE SYSTEM - QUICK START GUIDE

## THE PROBLEM
You were saying I can't hear you when you push-to-talk or use wake words. That's because I (running in Open Interpreter) wasn't connected to the voice input system.

## THE SOLUTION
I've created a **two-process system**:

1. **Voice Listener** (runs in separate window) - Listens for your voice
2. **Open Interpreter** (this session) - Can read what you said

---

## 🚀 HOW TO USE (EASIEST METHOD)

### Step 1: Start Voice Listener

**Option A - Double-click this:**
```
start_voice_monitoring.bat
```

**Option B - Or run manually:**
```bash
python voice_listener.py
```

Then choose:
- `1` for **Hotkey Mode** (Press Ctrl+Shift+Space to talk)
- `2` for **Wake Word Mode** (Say "Guppy" to activate)

### Step 2: Test It

**For Hotkey Mode:**
1. Press `Ctrl+Shift+Space`
2. Speak your command (you have 5 seconds)
3. Check the file `guppy_voice_commands.txt`

**For Wake Word Mode:**
1. Say "Guppy" or "Hey Guppy" or "Butler"
2. Wait for "Yes, Master Ryan?"
3. Speak your command
4. Check the file `guppy_voice_commands.txt`

### Step 3: I Read Your Commands

In this Open Interpreter session, I can check for your voice commands:

```python
python check_voice_commands.py
```

Or I can manually check the log file:

```python
# Read latest commands
with open("guppy_voice_commands.txt", "r") as f:
    print(f.read())
```

---

## 📁 FILES CREATED

### Main Files:
1. **voice_listener.py** - Background voice listener
2. **check_voice_commands.py** - Monitor for new commands
3. **start_voice_monitoring.bat** - Quick launcher
4. **guppy_voice_commands.txt** - Log file (created when you run listener)

### Supporting Files:
5. **guppy_voice_bridge.py** - Integration examples
6. **test_voice_system.py** - System diagnostics
7. **guppy_voice_demo.py** - Interactive testing
8. **VOICE_SYSTEM_STATUS.md** - Full documentation

---

## 🎯 RECOMMENDED WORKFLOW

### For Push-to-Talk:
1. Run `start_voice_monitoring.bat`
2. Choose option `1` (Hotkey Mode)
3. Keep that window open
4. In this Open Interpreter window, I can periodically check for new commands
5. Press `Ctrl+Shift+Space` whenever you want to speak to me
6. I'll see the transcribed text in the log file

### For Wake Word:
1. Run `start_voice_monitoring.bat`
2. Choose option `2` (Wake Word Mode)
3. Keep that window open
4. Just say "Guppy" whenever you want my attention
5. I'll see your commands in the log file

---

## 🔧 INTEGRATION WITH OPEN INTERPRETER

Currently, the voice system writes to a file and I can read from it. This is working but manual.

### Future Improvements (Optional):
1. **Real-time integration** - I could continuously monitor the file in background
2. **Direct Python integration** - Import the voice module directly
3. **API/Socket communication** - Real-time bidirectional communication
4. **Voice-activated responses** - I speak my responses automatically

Would you like me to implement any of these, sir?

---

## ⚙️ CUSTOMIZATION

### Change Hotkey:
Edit `voice_listener.py`, line with `listener.hotkey_mode()`:
```python
listener.hotkey_mode("ctrl+alt+v")  # Change to whatever you want
```

### Change Wake Words:
Edit `guppy_voice.py`, find:
```python
self.wake_words = ["guppy", "hey guppy", "butler"]
```
Add your preferred wake words.

### Change Listening Duration:
In `voice_listener.py`, change:
```python
self.voice.listen(duration=5)  # Change 5 to your preference
```

### Change Voice:
In `voice_listener.py`, initialization:
```python
self.voice = GuppyVoice(whisper_model="tiny", default_voice="bm_lewis")
```

Available voices: Check Kokoro documentation

---

## 🔍 TESTING RIGHT NOW

Let me test the current setup for you, Master Ryan.

### Test 1: Check if guppy_voice module works
```python
from guppy_voice import GuppyVoice
test = GuppyVoice(whisper_model="tiny")
test.speak("Testing, one, two, three.")
```

### Test 2: Start voice listener in background
```bash
start python voice_listener.py
```

### Test 3: Monitor for commands
```python
python check_voice_commands.py
```

---

## ❓ CURRENT LIMITATION

**The Issue:** I (Claude via Open Interpreter) am running in this terminal/chat interface. The voice listener needs to run in a separate window. They communicate via a log file.

**Why:** Python/Open Interpreter isn't designed for simultaneous voice listening while processing commands.

**Solution Options:**

1. **Current (File-based)** - Simple, works now ✅
   - You run voice_listener.py
   - I read the file
   - Pros: Reliable, simple
   - Cons: Not real-time, requires checking

2. **Background Thread** - Better integration
   - I could spawn a background thread
   - Continuously monitor voice
   - Pros: More integrated
   - Cons: More complex

3. **WebSocket Server** - Full integration
   - Voice listener as a service
   - I connect to it
   - Pros: Real-time, bidirectional
   - Cons: Most complex to set up

Which approach would you prefer, sir?

---

## 🎩 READY TO GO

**To start using voice RIGHT NOW:**

1. Open a new Command Prompt/Terminal
2. Navigate to: `C:\Users\Ryan\`
3. Run: `python voice_listener.py`
4. Choose mode (I recommend option 1 - Hotkey)
5. Use Ctrl+Shift+Space to talk to me
6. I'll check the log file when you ask

All systems prepared, Master Ryan. Voice capabilities are operational, just need you to start the listener.

🎩
