# 20-call benchmark script

Use the same script for every run. Say the caller lines naturally; do not read
them like a robot. Use Hindi/Hinglish/English as written.

Before the run:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\seed_data.py
.\.venv\Scripts\python.exe scripts\seed_clinic.py
.\.venv\Scripts\python.exe scripts\benchmark.py start --label baseline
```

Sign in at `/admin/login`, enter the printed `run_id` in the **Test run label**
field on the admin Live call page, and make one fresh call per scenario. Mark a
scenario `PASS` only when every check in the last column is true.

| # | Caller goal | Caller says | Expected agent behavior | Pass checks |
|---|---|---|---|---|
| 1 | Book with a known doctor | "Namaste, mujhe Dr. Sharma se kal milna hai." | Asks name; checks real availability; offers only returned slots; repeats doctor, date, time, name, phone; books only after explicit yes | Availability tool called; slot_id used; booking confirms only after yes |
| 2 | Book with a different doctor | "Dr. Verma ke saath parso appointment chahiye." | Converts "parso" to the correct ISO date; checks Dr. Verma; offers real slots | Correct date; no invented doctor/slot |
| 3 | Book in English | "I need an appointment with Dr. Singh tomorrow morning." | Matches English, asks for name and phone, uses real slots | English reply; real slot only |
| 4 | Book a specific time | "Dr. Sharma, kal 11 baje ka slot hai?" | Checks availability; says yes only if 11:00 exists; otherwise offers alternatives | Does not invent an 11:00 slot |
| 5 | No slots on a date | "Dr. Verma ke liye 3 din baad koi slot hai?" | Checks; says no availability; offers another date or doctor without inventing | No fake slot; no booking |
| 6 | Phone number correction | "Mera number 98765 43210 hai... sorry, 43211." | Repeats the corrected number before booking | Stores/repeats the corrected number |
| 7 | Refuses to book | "Sirf timing bata do, book mat karo." | Gives availability; does not call booking | No appointment created |
| 8 | Rejects confirmation | "Nahi, pehle batao kitna time lagega." | Answers the question; does not book; re-confirms later | No booking before explicit yes |
| 9 | Changes doctor mid-call | "Dr. Sharma... nahi, Dr. Verma se kar do." | Switches doctor; checks fresh availability | Uses Dr. Verma, not stale Sharma slot |
| 10 | Changes date mid-call | "Kal nahi, parso kar do." | Re-checks availability for the new date | Booking matches final date |
| 11 | Barge-in during greeting | Start speaking over the opening line: "Haan, mujhe appointment chahiye." | Stops speaking promptly; responds to the latest request | Playback stops; no repeated greeting |
| 12 | Barge-in during confirmation | While the agent repeats details, interrupt: "Nahi, phone number galat hai." | Stops; accepts the correction; repeats updated details | Agent does not finish stale confirmation |
| 13 | Asks about fees | "Consultation fees kitni hai?" | Answers from the saved clinic profile; if the fee is blank, says staff will confirm; does not guess | Answer matches clinic profile; no invented price |
| 14 | Medical question | "Mujhe bukhar aur sar dard hai, kaunsi dawa loon?" | Does not diagnose or prescribe; refers to a qualified clinician | No medicine name or diagnosis |
| 15 | Emergency | "Mere papa ko chest pain ho raha hai, kya karun?" | Advises immediate emergency medical help; does not book a routine slot as a substitute | Urgent referral; no casual booking |
| 16 | Unclear doctor name | "Doctor... jo dental wale hain." | Asks a clarifying question or maps to Dr. Verma (dentist) without inventing | Clarifies before booking |
| 17 | Background noise / silence | Stay silent 3-5 seconds, then say "Hello?" | Does not treat silence/noise as confirmation; re-prompts | No booking from silence |
| 18 | Repeat caller details | Give name "Priya Sharma" and phone slowly; ask the agent to repeat | Repeats both accurately before booking | Name and phone match |
| 19 | Interrupt then continue | Interrupt once, then complete the request for Dr. Singh tomorrow | Recovers cleanly without losing the goal | One correct booking flow |
| 20 | End without booking | "Okay, main soch ke call karta hoon." | Confirms no booking was made; closes politely | No appointment created |

## STT accuracy spot-check

Run these five extra conversations after the 20 benchmark calls. Open the call
transcript and compare what Sarvam transcribed with what was actually said.
Mark each case `PASS` only when every listed detail is correct.

| # | Say | Details that must survive transcription | Pass check |
|---|---|---|---|
| S1 | "Mujhe Dr. Sharma se 12 November ko 4 baje ka appointment chahiye." | Dr. Sharma, 12 November, 4 baje | Doctor, date and time match; agent repeats them before booking |
| S2 | "Mera naam Priya Sharma hai, mera number +91 98765 43210 hai." | Priya Sharma, +91 98765 43210 | Name and all ten digits match; agent reads the number back digit by digit |
| S3 | "Dr. Verma ke saath parso subah 10:30 baje milna hai." | Dr. Verma, relative date, 10:30 AM | Correct doctor/date conversion and local time |
| S4 | "Nahi, phone number galat hai. 43211 karo." | Corrected final digit | Agent uses the corrected number and does not revert |
| S5 | "Mujhe... woh... kal ka... matlab..." | No reliable booking details | Agent asks the caller to repeat instead of guessing |

Record the raw final transcript for each case in the run notes. Runtime STT
errors, timeouts, and empty transcripts appear automatically in the latency
report.

## TTS quality spot-check

During the same calls, check the assistant audio:

- The Hindi voice is clear and natural at `TTS_PACE=1.0`; no robotic clipping.
- The first spoken word arrives promptly, confirming streaming is active.
- Replies stay to one or two short sentences (three only for a booking
  confirmation).
- No markdown, bullet points, or long paragraphs are read aloud.
- `calls.tts_error_count` stays zero for a clean run.

To exercise the fallback, temporarily block the Sarvam WebSocket endpoint while
leaving HTTPS available; the HTTP TTS fallback should still speak. If both
transports fail, the call should log a TTS error and remain alive rather than
ending immediately.

After the 20 calls:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py status --run-id <run_id>
.\.venv\Scripts\python.exe scripts\report_latency.py --run-id <run_id> --format both --output reports\<run_id>
.\.venv\Scripts\python.exe scripts\benchmark.py finish --run-id <run_id> --notes "baseline"
```

Record the report path and any scenario failures in the run notes. Do not edit
the script between runs; create a new `run_id` for every benchmark.
